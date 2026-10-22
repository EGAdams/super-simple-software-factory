#!/usr/bin/env -S uv run
# /// script
# dependencies = ["pydantic", "python-dotenv", "pyyaml", "rich"]
# ///
"""ADW Interface Prompt — adw_prompt.py, decomposed to interfaces.

Same two phases (capture the request, dispatch it to an agent) but every
collaborator is reached through an abstract role instead of a concrete class:
each piece has exactly one reason to change, and none of them know about each
other's implementation. No `with` blocks anywhere — the one place that used
to need one (PhaseExecutor) drives the context-manager protocol by hand.

Usage:
    uv run adws/adw_interface_prompt.py "<prompt or path/to/prompt.md>" \
        [--agent builder] [--config adws/adw_sssf_config/sssf.config.yaml] [--adw-id a1b2c3d4]

Phases: engineer(request) -> <agent>
"""

from __future__ import annotations

import argparse
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

from adw_modules import agents, session, utils
from adw_modules.data_types import AgentCall, GenericOutput, PhaseParams, SSSFConfig
from adw_modules.runner import Run


# ─────────────────────────────────────────────────────────────────────────
# Roles (interfaces). Every collaborator below is reached through one of
# these — nothing in this file names a concrete class except at the one
# "composition root" at the bottom, where the wiring has to happen somewhere.
# ─────────────────────────────────────────────────────────────────────────

class IPhaseHandle( Protocol ):
    """The slice of runner.PhaseHandle a phase is allowed to touch.

    A phase could depend on `adw_modules.runner.PhaseHandle` directly, but
    that would make every phase implementation depend on the runner's
    concrete type. This Protocol is the seam: anything with the right two
    methods satisfies it, so phases are never coupled to how the runner
    builds its handle.
    """
    def log( self, **payload ) -> None: ...
    def call( self, call: AgentCall ): ...


class IPhase( ABC ):
    """A single named step of a run. One phase, one responsibility."""

    @property
    @abstractmethod
    def params( self ) -> PhaseParams:
        """Identity of this phase (name/kind/owner/description) — no behavior."""

    @abstractmethod
    def act( self, handle: IPhaseHandle ) -> None:
        """Do the phase's one job against the handle it was given."""


class IPhaseExecutor( ABC ):
    """Knows how to run an IPhase against a Run. Nothing else does."""

    @abstractmethod
    def execute( self, run: Run, phase: IPhase ) -> None: ...


class IConfigLoader( ABC ):
    """Loads and validates an SSSF config. Isolated so tests can fake it."""

    @abstractmethod
    def load( self, path: str ) -> SSSFConfig: ...

    @abstractmethod
    def validate( self, cfg: SSSFConfig, required_agents: list[ str ]) -> None: ...


class ISessionFactory( ABC ):
    """Builds (or joins) the Run for this process. Nothing else may."""

    @abstractmethod
    def create( self, cfg: SSSFConfig, adw_id: str | None ) -> Run: ...


class IPromptResolver( ABC ):
    """Turns the raw CLI argument into the literal prompt text."""

    @abstractmethod
    def resolve( self, raw: str ) -> str: ...


@dataclass( frozen=True )
class PromptRequest:
    """Parsed command-line intent. A value, not a behavior — no interface needed."""
    prompt: str
    agent: str
    config: str
    adw_id: str | None


class IArgumentParser( ABC ):
    """Turns argv into a PromptRequest. Knows argparse; nothing else does."""

    @abstractmethod
    def parse( self, argv: list[ str ]) -> PromptRequest: ...


class IApplication( ABC ):
    """The composition root's single entry point: run(argv) -> exit code."""

    @abstractmethod
    def run( self, argv: list[ str ]) -> int: ...


class ILifecycleLog( ABC ):
    """Where 'an object was constructed/destroyed' gets reported. One port,
    two very different sinks below — nobody writing a class needs to know
    which one it was handed.
    """

    @abstractmethod
    def created( self, obj: object ) -> None: ...

    @abstractmethod
    def destroyed( self, obj: object ) -> None: ...


class PrintLifecycleLog( ILifecycleLog ):
    """Bootstrap sink for objects born before a Run exists.

    Argv hasn't been parsed, the config that names the tracer's own db path
    hasn't been read yet — there is no central log to write into. This is
    the honest fallback for that window, not the central system itself.
    """

    def created( self, obj: object ) -> None:
        print( f"[lifecycle] + { type( obj ).__name__ } #{ id( obj ):x }" )

    def destroyed( self, obj: object ) -> None:
        print( f"[lifecycle] - { type( obj ).__name__ } #{ id( obj ):x }" )


class ConsoleLifecycleLog( ILifecycleLog ):
    """The real central sink: a Run's Console, same stream every phase and
    gate already reports through (stdout AND a `log` EventRecord in
    JSONL/SQLite). Only buildable once a Run exists.
    """

    def __init__( self, run: Run ):
        self._run = run

    def created( self, obj: object ) -> None:
        self._run.console.note( f"constructed { type( obj ).__name__ } #{ id( obj ):x }" )

    def destroyed( self, obj: object ) -> None:
        self._run.console.note( f"destroyed { type( obj ).__name__ } #{ id( obj ):x }" )


class LifecycleLogged:
    """Mixin: report your own birth at __init__, your own death at __del__.

    CPython collects an object the instant its refcount hits zero, so for
    the short-lived phase objects below (built, used, dropped within one
    expression) construction and destruction bracket `act()` exactly like a
    `with` block would — without being one. `__del__` at interpreter
    shutdown is a different story (globals may already be torn down), hence
    the swallow: a failed destruction log must never crash the destructor.
    """

    def __init__( self, logger: ILifecycleLog ):
        self._lifecycle_log = logger
        logger.created( self )

    def __del__( self ):
        try:
            self._lifecycle_log.destroyed( self )
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────
# Phases. Each one is the smallest possible IPhase: a name/kind/owner triple
# plus exactly one call against the handle. Compare to the original, where
# "capture the request" and "send it to the agent" were two bodies of a
# single function sharing a closure — here neither phase can reach into the
# other's state because neither has any.
# ─────────────────────────────────────────────────────────────────────────

class RequestCapturePhase( LifecycleLogged, IPhase ):
    """The GetInputPhase: records the incoming ask, nothing more."""

    def __init__( self, engineer: str, prompt: str, logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )
        self._engineer = engineer
        self._prompt = prompt

    @property
    def params( self ) -> PhaseParams:
        return PhaseParams( name="request", kind="engineer", owner=self._engineer, description="Capture the incoming ask" )

    def act( self, handle: IPhaseHandle ) -> None:
        handle.log( input=self._prompt )


class AgentDispatchPhase( LifecycleLogged, IPhase ):
    """The SendRequestPhase: hands the prompt to one agent, nothing more."""

    def __init__( self, agent: str, prompt: str, logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )
        self._agent = agent
        self._prompt = prompt

    @property
    def params( self ) -> PhaseParams:
        return PhaseParams( name="prompt", kind="agent", owner=self._agent,
                           description=f"Send the request straight to { self._agent } "
                                       f"and parse its envelope" )

    def act( self, handle: IPhaseHandle ) -> None:
        handle.call( AgentCall( output_type=GenericOutput, prompt=self._prompt ))


# ─────────────────────────────────────────────────────────────────────────
# Adapters. Each one wraps exactly one existing concrete thing behind one of
# the interfaces above — this is where "programming to the implementation"
# gets pushed to the edges instead of spreading through the phases.
# ─────────────────────────────────────────────────────────────────────────

class ManualContextPhaseExecutor( LifecycleLogged, IPhaseExecutor ):
    """Runs a phase without ever writing the word `with`.

    `run.phase(...)` is a @contextmanager — a generator wrapped so that
    `with run.phase(p) as ph: ...` drives it. A `with` statement is just
    sugar for calling `__enter__`, running the body, then calling `__exit__`
    (passing the exception info on failure, None-triple on success). Doing
    that by hand is exactly as correct and uses none of the sugar.
    """

    def __init__( self, logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )

    def execute( self, run: Run, phase: IPhase ) -> None:
        phase_cm = run.phase( phase.params )
        handle = phase_cm.__enter__()
        try:
            result = phase.act( handle )
        except BaseException as error:
            if phase_cm.__exit__( type( error ), error, error.__traceback__ ):
                return result
            raise
        else:
            phase_cm.__exit__( None, None, None )
            return result


class SssfConfigLoader( LifecycleLogged, IConfigLoader ):
    """The only class in this file allowed to know `adw_modules.agents` loads YAML."""

    def __init__( self, logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )

    def load( self, path: str ) -> SSSFConfig:
        return agents.load_config( path )

    def validate( self, cfg: SSSFConfig, required_agents: list[ str ]) -> None:
        agents.validate( cfg, required_agents )


class SessionRunFactory( LifecycleLogged, ISessionFactory ):
    """The only class allowed to know a Run comes from `adw_modules.session.ensure`."""

    def __init__( self, logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )

    def create( self, cfg: SSSFConfig, adw_id: str | None ) -> Run:
        return session.ensure( cfg, adw_id )


class FileOrInlinePromptResolver( LifecycleLogged, IPromptResolver ):
    """The only class allowed to know a prompt might secretly be a file path."""

    def __init__( self, logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )

    def resolve( self, raw: str ) -> str:
        return utils.resolve_prompt( raw )


class ArgparseArgumentParser( LifecycleLogged, IArgumentParser ):
    """The only class allowed to know this CLI is built on argparse."""

    def __init__( self, description: str, logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )
        self._description = description

    def parse( self, argv: list[ str ]) -> PromptRequest:
        parser = argparse.ArgumentParser( description=self._description )
        parser.add_argument( "prompt", help="inline text or a path to a prompt file" )
        parser.add_argument( "--agent", default="builder", help="agent name from the config" )
        parser.add_argument( "--config", default="adws/adw_sssf_config/sssf.config.yaml" )
        parser.add_argument( "--adw-id", default=None, help="join or pin an existing session" )
        parsed = parser.parse_args( argv )
        return PromptRequest( prompt=parsed.prompt, agent=parsed.agent,
                             config=parsed.config, adw_id=parsed.adw_id )


# ─────────────────────────────────────────────────────────────────────────
# Composition root. The only place that is allowed to know every interface
# AND every concrete adapter — everything above it talks only to roles.
# ─────────────────────────────────────────────────────────────────────────

class PromptApplication( LifecycleLogged, IApplication ):
    """Orchestrates the two-phase run. Depends only on interfaces (DIP)."""

    def __init__( self,
                  argument_parser: IArgumentParser,
                  prompt_resolver: IPromptResolver,
                  config_loader: IConfigLoader,
                  session_factory: ISessionFactory,
                  phase_executor: IPhaseExecutor,
                  logger: ILifecycleLog ):
        LifecycleLogged.__init__( self, logger )
        self._argument_parser = argument_parser
        self._prompt_resolver = prompt_resolver
        self._config_loader = config_loader
        self._session_factory = session_factory
        self._phase_executor = phase_executor

    def run( self, argv: list[ str ]) -> int:
        request = self._argument_parser.parse( argv )
        prompt = self._prompt_resolver.resolve( request.prompt )

        cfg = self._config_loader.load( request.config )
        self._config_loader.validate( cfg, [ request.agent ])
        run = self._session_factory.create( cfg, request.adw_id )

        session_log: ILifecycleLog = ConsoleLifecycleLog( run )

        self._phase_executor.execute( run, RequestCapturePhase( run.engineer, prompt, session_log ))
        self._phase_executor.execute( run, AgentDispatchPhase( request.agent, prompt, session_log ))

        return run.finish()


def build_application() -> IApplication:
    """Wire the concrete adapters into the application. The one spot that may."""
    bootstrap_log: ILifecycleLog = PrintLifecycleLog()
    return PromptApplication(
        argument_parser=ArgparseArgumentParser( __doc__, bootstrap_log ),
        prompt_resolver=FileOrInlinePromptResolver( bootstrap_log ),
        config_loader=SssfConfigLoader( bootstrap_log ),
        session_factory=SessionRunFactory( bootstrap_log ),
        phase_executor=ManualContextPhaseExecutor( bootstrap_log ),
        logger=bootstrap_log,
    )


if __name__ == "__main__":
    sys.exit( build_application().run( sys.argv[ 1: ]))
