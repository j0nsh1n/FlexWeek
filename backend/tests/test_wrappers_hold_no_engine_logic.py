"""Wrappers that are not listed as STAYS or LOGIC in docs/engine/adapters.md stay free of engine logic."""

from __future__ import annotations

import ast
from pathlib import Path

BACKEND_MODULES = (
    "assignments",
    "availability",
    "comfort",
    "day",
    "explain",
    "limits",
    "month",
    "recovery",
    "restore",
    "slots",
    "solver",
    "storage",
    "transfer",
    "weeks",
)
DESKTOP_MODULES = (
    "calendar",
    "custom_look",
    "files",
    "focus",
    "history",
    "pomodoro",
    "remind",
    "reuse",
    "tokens",
    "update",
    "version",
    "weekmodel",
)
# look.py still paints. Only the four helpers that call the engine are wrappers.
LOOK_HELPERS = (
    "known_pack",
    "sanitize_custom",
    "sanitize_look",
    "effective_look",
)
APP_MODULES = ("app",)
# The helper functions of backend/app.py that hold no HTTP: route handlers and the functions that
# map an engine status onto an HTTP error are not listed and are not checked.
APP_HELPERS = (
    "adopt_legacy_deadlines",
    "encode_new_assignment",
    "rewrite_blocks",
    "normalize_stored_block",
    "rewrite_stored_blocks",
    "assignment_view",
    "require_own_assignments",
)

ROOT = Path(__file__).resolve().parents[2]
ADAPTERS = ROOT / "docs" / "engine" / "adapters.md"


def names_from_doc(*kinds: str) -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for line in ADAPTERS.read_text().splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 3 or cells[2] not in kinds:
            continue
        found.setdefault(cells[0], set()).add(cells[1])
    return found


def _is_class(name: str) -> bool:
    return name.rsplit(".", 1)[-1][:1].isupper()


def is_stays(names: set[str], qual: str) -> bool:
    """A listed function, and functions nested inside it.

    A class listed as STAYS is the definition. Its methods are classified on their own rows, so the
    class name does not exempt them. Nested functions under a listed function still are.
    """
    parts = qual.split(".")
    for end in range(1, len(parts) + 1):
        prefix = ".".join(parts[:end])
        if prefix in names and not _is_class(prefix):
            return True
    return False


def is_none_check(node: ast.Compare) -> bool:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        return False
    if not isinstance(node.ops[0], (ast.Is, ast.IsNot)):
        return False
    other = node.comparators[0]
    return isinstance(other, ast.Constant) and other.value is None


def is_sort(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name) and func.id == "sorted":
        return True
    return isinstance(func, ast.Attribute) and func.attr == "sort"


def is_type_test(node: ast.Call) -> bool:
    func = node.func
    return isinstance(func, ast.Name) and func.id in {"isinstance", "type"}


def is_truth_test(node: ast.expr) -> bool:
    """`if name` or `if obj.attr`: the value's own truth, not a comparison."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        node = node.operand
    return isinstance(node, (ast.Name, ast.Attribute))


def logic_in(node: ast.AST, qual: str, stays: set[str]) -> list[str]:
    problems: list[str] = []

    def walk(item: ast.AST) -> None:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested = f"{qual}.{item.name}"
            if not is_stays(stays, nested):
                problems.extend(logic_in(item, nested, stays))
            return
        if isinstance(item, ast.Lambda):
            walk(item.body)
            return
        kind = None
        if isinstance(item, (ast.For, ast.While, ast.AsyncFor)):
            kind = "loop"
        elif isinstance(item, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) and any(
            gen.ifs for gen in item.generators
        ):
            kind = "comprehension"
        elif isinstance(item, (ast.BinOp, ast.AugAssign)):
            kind = "arithmetic"
        elif isinstance(item, ast.Compare) and not is_none_check(item):
            kind = "comparison"
        elif isinstance(item, ast.Call) and is_sort(item):
            kind = "sort"
        elif isinstance(item, ast.Call) and is_type_test(item):
            kind = "type test"
        elif isinstance(item, ast.BoolOp):
            kind = "default"
        elif isinstance(item, ast.IfExp):
            kind = "branch"
        elif isinstance(item, (ast.If, ast.While)) and is_truth_test(item.test):
            kind = "truth test"
        if kind is not None:
            problems.append(
                f"{qual}: logic belongs in the engine: see docs/engine/adapters.md ({kind})"
            )
        for child in ast.iter_child_nodes(item):
            walk(child)

    body = node.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else [node]
    for stmt in body:
        walk(stmt)
    return problems


def functions_of(tree: ast.AST, stays: set[str]) -> list[str]:
    problems: list[str] = []

    def scan(body: list[ast.stmt], prefix: str) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                scan(node.body, f"{prefix}{node.name}.")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{node.name}"
                if not is_stays(stays, qual):
                    problems.extend(logic_in(node, qual, stays))

    if isinstance(tree, ast.Module):
        scan(tree.body, "")
    return problems


# The stricter shapes (a type test, `x or default`, a conditional expression, a truth test) already
# sit in these wrappers. Each line names the shape. A new shape, or an older one (a loop, arithmetic,
# a comparison, a sort), is not listed and still fails.
ALLOWED_FOR_NOW = {
    ("assignments.prepare_solve", "branch"),  # a missing deadline stays None while decoding
    ("availability.resolve_work_windows", "branch"),  # None windows stay None on the way in
    ("solver._points", "branch"),  # a missing point stays None while encoding
    ("calendar.apply_block_times", "branch"),  # the engine's None answer stays None
    ("calendar.relocate_block", "branch"),  # None dest in, None answer out
    ("calendar.placement_on", "branch"),  # None trace in; the engine's flag becomes NOT_TODAY
    ("calendar.agenda_for", "branch"),  # None trace and day data stay None on the way in
    ("calendar.next_action_for", "branch"),  # None day data stays None on the way in
    ("calendar.span_problem", "type test"),  # the engine is told the due value's Python type
    ("custom_look._text_or_none", "branch"),  # text stays, anything else becomes None
    ("custom_look._text_or_none", "type test"),
    ("custom_look._name", "branch"),  # a non-text name is none for the engine
    ("custom_look._name", "type test"),
    ("custom_look.sanitize_saved", "branch"),  # a non-list file is an empty list
    ("custom_look.sanitize_saved", "type test"),
    ("custom_look.save_look", "branch"),  # a non-text name is an empty string
    ("custom_look.save_look", "type test"),
    ("custom_look.free_name", "branch"),  # a non-text name is an empty string
    ("custom_look.free_name", "type test"),
    ("custom_look.rename_look", "branch"),  # a non-text name is an empty string
    ("custom_look.rename_look", "type test"),
    ("focus.persist_payload", "branch"),  # the engine's None answer stays None
    ("focus.restore_state", "branch"),  # the engine's None answer stays None
    ("focus.credit_target", "branch"),  # the engine's None answer stays None
    ("history.capture_step", "branch"),  # the engine's None answer stays None
    ("reuse.apply_plan", "branch"),  # None targets and assignments stay None on the way in
    ("reuse.due_point", "branch"),  # the engine's None answer stays None
    ("reuse.block_occurs_on_day", "branch"),  # None placed blocks stay None on the way in
    ("reuse.row_conflict", "branch"),  # the engine's None answer stays None
    ("update.available", "branch"),  # the engine's None answer stays None
    ("update.release_from_page", "branch"),  # the engine's None answer stays None
    ("weekmodel.WeekModel._engine", "default"),  # either tuple missing skips the handle cache
    ("weekmodel.WeekModel._engine", "type test"),
    ("weekmodel.WeekModel.on_day", "default"),  # either tuple missing skips the day cache
    ("weekmodel.WeekModel.on_day", "type test"),
    ("weekmodel.WeekModel.load_min", "default"),  # either tuple missing skips the load cache
    ("weekmodel.WeekModel.load_min", "type test"),
    ("weekmodel.WeekModel.day_queue", "branch"),  # no current block stays None
    ("app.adopt_legacy_deadlines", "truth test"),  # the engine's "over the cap" becomes the 422
    ("app.require_own_assignments", "truth test"),  # the engine's "not owned" becomes the 422
    ("app.insert_restore_point", "default"),  # a missing keep-set is an empty list
}


def problem_key(problem: str) -> tuple[str, str]:
    name = problem.split(":", 1)[0]
    kind = problem.rsplit("(", 1)[-1].removesuffix(")")
    return name, kind


def test_wrappers_keep_no_engine_logic() -> None:
    # LOGIC is a leftover the table names (custom_look.readability). LOGIC, moved is not exempt.
    exempt = names_from_doc("STAYS", "LOGIC")
    problems: list[str] = []
    modules = [(name, ROOT / "backend" / f"{name}.py") for name in BACKEND_MODULES]
    modules += [(name, ROOT / "desktop" / "native" / f"{name}.py") for name in DESKTOP_MODULES]
    for name, path in modules:
        tree = ast.parse(path.read_text(), filename=str(path))
        for problem in functions_of(tree, exempt.get(name, set())):
            problems.append(f"{name}.{problem}")
    look_path = ROOT / "desktop" / "native" / "look.py"
    look_tree = ast.parse(look_path.read_text(), filename=str(look_path))
    assert isinstance(look_tree, ast.Module)
    listed = {
        node.name: node
        for node in look_tree.body
        if isinstance(node, ast.FunctionDef) and node.name in LOOK_HELPERS
    }
    missing = set(LOOK_HELPERS) - listed.keys()
    assert not missing, f"look.py no longer defines: {sorted(missing)}"
    for name in LOOK_HELPERS:
        for problem in logic_in(listed[name], name, set()):
            problems.append(f"look.{problem}")
    problems = [problem for problem in problems if problem_key(problem) not in ALLOWED_FOR_NOW]
    assert not problems, "\n".join(problems)


def test_app_helpers_keep_no_engine_logic() -> None:
    path = ROOT / "backend" / f"{APP_MODULES[0]}.py"
    tree = ast.parse(path.read_text(), filename=str(path))
    assert isinstance(tree, ast.Module)
    listed = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in APP_HELPERS
    }
    missing = set(APP_HELPERS) - listed.keys()
    assert not missing, f"app.py no longer defines: {sorted(missing)}"
    problems: list[str] = []
    for name in APP_HELPERS:
        problems.extend(f"app.{problem}" for problem in logic_in(listed[name], name, set()))
    problems = [problem for problem in problems if problem_key(problem) not in ALLOWED_FOR_NOW]
    assert not problems, "\n".join(problems)


ROUTE_VERBS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}
# Ways to register a route other than `@app.<verb>(path)`; app.py uses none of them, so the scan below sees
# every route.
OTHER_ROUTE_WAYS = {"api_route", "add_api_route", "add_route", "include_router", "websocket", "mount"}
Handler = ast.FunctionDef | ast.AsyncFunctionDef


def app_tree() -> ast.Module:
    path = ROOT / "backend" / "app.py"
    return ast.parse(path.read_text(), filename=str(path))


def route_handlers(tree: ast.Module) -> list[tuple[str, Handler]]:
    """Every function `create_app` registers with `@app.<verb>(path)`, with its path."""
    found: list[tuple[str, Handler]] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue
            target = decorator.func
            if isinstance(target.value, ast.Name) and target.value.id == "app" and target.attr in ROUTE_VERBS:
                route = decorator.args[0]
                assert isinstance(route, ast.Constant) and isinstance(route.value, str), node.name
                found.append((f"{target.attr.upper()} {route.value}", node))
    return found


# Each shape a route or a shared route helper may keep, with why.
ROUTE_SHAPES_ALLOWED = {
    ("get_week", "branch"),  # a week not asked for is this week, read from the one clock
    ("get_storage_info", "default"),  # the server's own address; goes with the server in P2
    ("get_storage_info", "comparison"),
    ("authenticate", "branch"),  # picks the Rust sign-up or sign-in call
}
# Routes that answer without calling Rust, with why.
ROUTES_WITHOUT_RUST = {
    "me",  # the signed-in account is the session check's own answer, and that check is Rust
    "health",  # says the server is up; goes with the server in P2
    "get_storage_info",  # the server's address and body limit; goes with the server in P2
}
# Routes that call Rust and then answer with the signed-in account (who the window is), with why.
ROUTES_ANSWERING_THE_ACCOUNT = {
    "change_password",  # the new password is saved by Rust; the window stays the same account
}
# app.py helpers every data route goes through; their bodies are held to the same checks.
SHARED_ROUTE_HELPERS = ("served", "authenticate")
# A helper handed the Rust function to call, and the parameter that holds it. Every call of it must hand it
# a Rust function.
RUST_FUNCTION_TAKERS = {"served": "call"}


def is_engine(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "flexweek_engine"
    )


def own_body(node: Handler) -> list[ast.AST]:
    """The function's own statements and expressions, without the bodies of lambdas or nested functions."""
    found: list[ast.AST] = []

    def walk(item: ast.AST) -> None:
        found.append(item)
        for child in ast.iter_child_nodes(item):
            if not isinstance(child, (ast.Lambda, ast.FunctionDef, ast.AsyncFunctionDef)):
                walk(child)

    for statement in node.body:
        walk(statement)
    return found


def assigned(node: Handler) -> list[tuple[list[ast.expr], ast.expr | None]]:
    """Each assignment in the function's own body: its targets and its value (None for `x += ...`)."""
    found: list[tuple[list[ast.expr], ast.expr | None]] = []
    for item in own_body(node):
        if isinstance(item, ast.Assign):
            found.append((list(item.targets), item.value))
        elif isinstance(item, ast.AnnAssign):
            found.append(([item.target], item.value))
        elif isinstance(item, ast.AugAssign):
            found.append(([item.target], None))
    return found


def target_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Subscript):
        return target_names(target.value)
    return {part.id for part in ast.walk(target) if isinstance(part, ast.Name)}


def is_engine_choice(value: ast.expr) -> bool:
    if isinstance(value, ast.IfExp):
        return is_engine_choice(value.body) and is_engine_choice(value.orelse)
    return is_engine(value)


class RustAnswers:
    """Which calls reach Rust and which values are Rust's answer, inside one function."""

    def __init__(self, node: Handler, rust_helpers: set[str]) -> None:
        self.rust_helpers = rust_helpers
        self.engine: set[str] = set()
        takes = RUST_FUNCTION_TAKERS.get(node.name)
        if takes is not None:
            self.engine.add(takes)
        assignments = assigned(node)
        # A name bound to a Rust function only counts when nothing else is ever assigned to it.
        chosen = {
            name
            for targets, value in assignments
            if value is not None and is_engine_choice(value)
            for target in targets
            for name in target_names(target)
        }
        other = {
            name
            for targets, value in assignments
            if value is None or not is_engine_choice(value)
            for target in targets
            for name in target_names(target)
        }
        self.engine |= chosen - other
        # A name holds Rust's answer when every assignment to it (or into it) is from Rust and no method is
        # called on it or on a name that holds the same value (`answer.clear()`, or through `alias = answer`).
        aliases: dict[str, set[str]] = {}
        for targets, value in assignments:
            if not isinstance(value, ast.Name):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    group = aliases.get(target.id, {target.id}) | aliases.get(value.id, {value.id})
                    for member in group:
                        aliases[member] = group
        changed = {
            member
            for item in own_body(node)
            if isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
            and isinstance(item.func.value, ast.Name)
            for member in aliases.get(item.func.value.id, {item.func.value.id})
        }
        self.bound: set[str] = set()
        while True:
            tainted: set[str] = set()
            for targets, value in assignments:
                if value is not None and self.from_rust(value):
                    continue
                for target in targets:
                    names = target_names(target)
                    # A store into the value (`x[k] = ...`, `x += ...`) changes it under every name it has.
                    if value is None or isinstance(target, (ast.Subscript, ast.Attribute)):
                        names = {member for name in names for member in aliases.get(name, {name})}
                    tainted |= names
            grown = (
                {
                    name
                    for targets, value in assignments
                    if value is not None and self.from_rust(value)
                    for target in targets
                    for name in target_names(target)
                }
                - tainted
                - self.engine
                - changed
            )
            if grown <= self.bound:
                break
            self.bound |= grown

    def is_rust(self, part: ast.AST) -> bool:
        return is_engine(part) or (isinstance(part, ast.Name) and part.id in self.engine)

    def is_rust_call(self, call: ast.Call) -> bool:
        if self.is_rust(call.func):
            return True
        if isinstance(call.func, ast.Name) and call.func.id in RUST_FUNCTION_TAKERS:
            return bool(call.args) and self.is_rust(call.args[0])
        return isinstance(call.func, ast.Name) and call.func.id in self.rust_helpers

    def from_rust(self, value: ast.expr) -> bool:
        if isinstance(value, ast.Call):
            decoded = (
                isinstance(value.func, ast.Attribute)
                and isinstance(value.func.value, ast.Name)
                and (value.func.value.id, value.func.attr) == ("json", "loads")
            )
            counted = isinstance(value.func, ast.Name) and value.func.id == "len"
            if decoded or counted:
                return bool(value.args) and self.from_rust(value.args[0])
            return self.is_rust_call(value)
        if isinstance(value, ast.Name):
            return value.id in self.bound
        if isinstance(value, ast.Dict):
            return bool(value.values) and all(self.from_rust(part) for part in value.values)
        if isinstance(value, ast.Subscript):
            return self.from_rust(value.value)
        return False

    def calls_rust(self, node: Handler) -> bool:
        return any(isinstance(item, ast.Call) and self.is_rust_call(item) for item in own_body(node))


def answers_with_the_account(value: ast.expr) -> bool:
    """`{"id": account["id"], ...}`: every value is a field of the signed-in account the session check gave."""
    return (
        isinstance(value, ast.Dict)
        and bool(value.values)
        and all(
            isinstance(part, ast.Subscript)
            and isinstance(part.value, ast.Name)
            and part.value.id == "account"
            for part in value.values
        )
    )


def answers_from_rust(node: Handler, rust_helpers: set[str]) -> bool:
    """Every value the function returns is Rust's answer. A function that returns nothing (a 204 route), or
    answers with the signed-in account, still has to call Rust itself."""
    rust = RustAnswers(node, rust_helpers)
    returned = [
        item.value for item in own_body(node) if isinstance(item, ast.Return) and item.value is not None
    ]
    if node.name in ROUTES_ANSWERING_THE_ACCOUNT:
        return rust.calls_rust(node) and all(answers_with_the_account(value) for value in returned)
    if not returned:
        return rust.calls_rust(node)
    return all(rust.from_rust(value) for value in returned)


def test_routes_only_decode_call_and_encode() -> None:
    tree = app_tree()
    other_ways = sorted(
        {
            item.attr
            for item in ast.walk(tree)
            if isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == "app"
            and item.attr in OTHER_ROUTE_WAYS
        }
    )
    assert not other_ways, f"app.py registers routes another way the scan does not read: {other_ways}"
    handlers = route_handlers(tree)
    assert len(handlers) > 30, "the route scan found too few routes"
    routes = {node.name for _, node in handlers}
    helpers = {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name not in routes
    }
    problems: list[str] = []
    # The helpers whose answer is Rust's, found until no more join (one may answer through another).
    rust_helpers: set[str] = set()
    while True:
        grown = {
            name
            for name, node in helpers.items()
            if name not in RUST_FUNCTION_TAKERS and answers_from_rust(node, rust_helpers)
        }
        if grown <= rust_helpers:
            break
        rust_helpers |= grown
    for name in SHARED_ROUTE_HELPERS:
        if not answers_from_rust(helpers[name], rust_helpers):
            problems.append(f"helper {name}: answers without the Rust service's answer")
    for taker in RUST_FUNCTION_TAKERS:
        for node in [*helpers.values(), *(node for _, node in handlers)]:
            rust = RustAnswers(node, rust_helpers)
            for item in own_body(node):
                if not (isinstance(item, ast.Call) and isinstance(item.func, ast.Name)):
                    continue
                if item.func.id == taker and not (item.args and rust.is_rust(item.args[0])):
                    problems.append(f"{node.name}: {taker} is handed something other than a Rust function")
    checked: list[tuple[str, Handler]] = list(handlers)
    checked += [(f"helper {name}", helpers[name]) for name in SHARED_ROUTE_HELPERS]
    for route, node in checked:
        for problem in logic_in(node, node.name, set()):
            if problem_key(problem) not in ROUTE_SHAPES_ALLOWED:
                problems.append(f"{route} {problem}")
    for route, node in handlers:
        if node.name not in ROUTES_WITHOUT_RUST and not answers_from_rust(node, rust_helpers):
            problems.append(f"{route} {node.name}: answers without the Rust service's answer")
    assert not problems, "\n".join(problems)
