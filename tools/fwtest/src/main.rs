//! fwtest: FlexWeek's test harness. The contract is docs/tooling/fwtest.md.

use clap::{Args, Parser, Subcommand};

#[derive(Parser)]
#[command(name = "fwtest", about = "Run FlexWeek checks one job at a time")]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

/// Where `--touched` takes the changed paths from.
#[derive(Args, Default)]
struct ChangeArgs {
    /// Compare with this ref's merge base. Default: origin/main, then main.
    #[arg(long, value_name = "REF", conflicts_with = "paths_from")]
    base: Option<String>,
    /// Read the changed paths from this file, one per line, instead of git.
    #[arg(long, value_name = "FILE")]
    paths_from: Option<std::path::PathBuf>,
}

impl ChangeArgs {
    fn change(self) -> fwtest::select::Change {
        fwtest::select::Change {
            base: self.base,
            paths_from: self.paths_from,
        }
    }

    fn given(&self) -> bool {
        self.base.is_some() || self.paths_from.is_some()
    }
}

#[derive(Subcommand)]
enum Command {
    /// Stop processes left by a finished job and drop its record.
    Clean,
    /// Run ruff, mypy, pytest and the diff whitespace checks.
    Gate {
        /// Skip the desktop import check and run only backend/tests.
        #[arg(long, conflicts_with = "touched")]
        backend_only: bool,
        /// Run only the tests the changed paths select (see `fwtest select`).
        #[arg(long)]
        touched: bool,
        #[command(flatten)]
        change: ChangeArgs,
        /// Pytest workers. Default is half the cores, and at least 2.
        #[arg(long)]
        workers: Option<u32>,
        /// Python interpreter. Overrides FWTEST_PYTHON and .venv/bin/python.
        #[arg(long)]
        python: Option<std::path::PathBuf>,
    },
    /// Break one rule at a time and check that its test goes red.
    Mutate {
        /// Run only the case with this name.
        #[arg(long)]
        case: Option<String>,
        /// Python interpreter. Overrides FWTEST_PYTHON and .venv/bin/python.
        #[arg(long)]
        python: Option<std::path::PathBuf>,
        /// Command that installs the engine into this checkout's .venv.
        /// Overrides FWTEST_ENGINE_BUILD. The checkout is the working directory.
        /// `off` skips the rebuild.
        #[arg(long)]
        engine_build: Option<String>,
        /// Apply an engine mutation but do not rebuild the installed module.
        #[arg(long)]
        no_engine_rebuild: bool,
        /// Run only cases whose file is under engine/.
        #[arg(long)]
        engine_only: bool,
        /// Run shard K of N after the existing case order (1-based K, as K/N).
        #[arg(long, value_name = "K/N", value_parser = fwtest::mutate::parse_shard)]
        shard: Option<fwtest::mutate::Shard>,
        /// Spec files. Default is every scripts/mutations/*.json in the checkout.
        specs: Vec<std::path::PathBuf>,
    },
    /// Start the hidden session, run the rig driver, then stop that session.
    Rig {
        /// Python interpreter. Overrides FWTEST_PYTHON and .venv/bin/python.
        #[arg(long)]
        python: Option<std::path::PathBuf>,
        /// Arguments forwarded to scripts/rig/drive.py.
        #[arg(trailing_var_arg = true, allow_hyphen_values = true)]
        args: Vec<String>,
    },
    /// Run a command as one contained job. A pytest command reruns a failed test alone once.
    Run {
        /// Stop the job after this many seconds (exit 124).
        #[arg(long)]
        timeout: Option<u64>,
        /// Add the test paths the changed paths select to the pytest command.
        #[arg(long)]
        touched: bool,
        #[command(flatten)]
        change: ChangeArgs,
        /// Command to run. Put it after `--`.
        #[arg(last = true, required = true, num_args = 1..)]
        command: Vec<String>,
    },
    /// Print what the changed paths select: test areas, pytest paths, cargo packages,
    /// mutation cases and picture areas.
    Select {
        #[command(flatten)]
        change: ChangeArgs,
    },
    /// Summarise the flaky-test log, most frequent first.
    Flaky {
        /// Log file. Overrides FWTEST_FLAKY_LOG and the scratch folder's log.
        #[arg(long)]
        log: Option<std::path::PathBuf>,
    },
}

fn needs_touched(touched: bool, change: &ChangeArgs) -> Option<u8> {
    if !touched && change.given() {
        eprintln!("--base and --paths-from go with --touched");
        return Some(2);
    }
    None
}

fn main() {
    let mut args = std::env::args();
    let _argv0 = args.next();
    if args.next().as_deref() == Some("--inside-rig") {
        let rest: Vec<String> = args.collect();
        std::process::exit(fwtest::rig::inside(&rest));
    }
    let cli = Cli::parse();
    let code = match cli.command {
        Command::Clean => fwtest::clean::run().0,
        Command::Gate {
            backend_only,
            touched,
            change,
            workers,
            python,
        } => match needs_touched(touched, &change) {
            Some(code) => code,
            None => {
                let change = touched.then(|| change.change());
                fwtest::gate::run(backend_only, workers, python.as_deref(), change.as_ref())
            }
        },
        Command::Mutate {
            case,
            python,
            engine_build,
            no_engine_rebuild,
            engine_only,
            shard,
            specs,
        } => fwtest::mutate::run(
            &specs,
            case.as_deref(),
            python.as_deref(),
            engine_build.as_deref(),
            no_engine_rebuild,
            engine_only,
            shard,
        ),
        Command::Rig { python, args } => fwtest::rig::run(&args, python.as_deref()),
        Command::Run {
            timeout,
            touched,
            change,
            command,
        } => match needs_touched(touched, &change) {
            Some(code) => code,
            None => {
                let change = touched.then(|| change.change());
                fwtest::select_run::run(&command, timeout, change.as_ref())
            }
        },
        Command::Select { change } => fwtest::select::run(&change.change()),
        Command::Flaky { log } => fwtest::flaky::run(log.as_deref()),
    };
    std::process::exit(i32::from(code));
}
