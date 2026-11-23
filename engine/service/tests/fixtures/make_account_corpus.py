"""The account request parity corpus: generated names, passwords and recovery codes, and what the server's
pydantic models make of each (Credentials for sign-up and sign-in, RecoverRequest, PasswordChange): the fields
as read, or a refusal. Fixed seed. Run with the project venv from the repository root:
PYTHONPATH=. .venv/bin/python <this file> <out.json> 1500."""

import json
import random
import sys

from pydantic import ValidationError

from backend.app import Credentials, PasswordChange, RecoverRequest

rng = random.Random(20261122)
# Letters a name may hold, and ones that look like them: Unicode letters and digits, the Kelvin sign (which
# lowercases to "k"), the long s, a dash, spaces and a newline.
NAME_PARTS = list("abcxyzABCXYZ0189_") + ["é", "ß", "ſ", "K", "٣", "１", "-", " ", "\n", "\t", "."]
TEXT_PARTS = list("abcXYZ019 _-!") + ["é", "日", "😀", "\n", "\u0000", "​"]
NAME_LENGTHS = [0, 1, 2, 3, 4, 16, 31, 32, 33, 40]
PASSWORD_LENGTHS = [0, 5, 11, 12, 13, 64, 127, 128, 129, 140]
CODE_LENGTHS = [0, 7, 8, 9, 19, 63, 64, 65, 70]


def text(parts: list[str], lengths: list[int]) -> str:
    size = rng.choice(lengths)
    return "".join(rng.choice(parts) for _ in range(size))


def name() -> str:
    if rng.random() < 0.5:
        # Mostly well-formed names, so enough are accepted to compare what each side keeps.
        return "".join(rng.choice("abcXYZ019_") for _ in range(rng.choice([3, 8, 32])))
    return text(NAME_PARTS, NAME_LENGTHS)


def read(model: type, fields: dict) -> dict | None:
    try:
        return model.model_validate(fields).model_dump()
    except ValidationError:
        return None


def case() -> dict:
    fields = {
        "username": name(),
        "password": text(TEXT_PARTS, PASSWORD_LENGTHS),
        "code": text(TEXT_PARTS, CODE_LENGTHS),
        "new_password": text(TEXT_PARTS, PASSWORD_LENGTHS),
    }
    credentials = read(Credentials, {"username": fields["username"], "password": fields["password"]})
    recover = read(
        RecoverRequest,
        {"username": fields["username"], "code": fields["code"], "password": fields["password"]},
    )
    change = read(
        PasswordChange,
        {"current_password": fields["password"], "new_password": fields["new_password"]},
    )
    return {"input": fields, "credentials": credentials, "recover": recover, "change": change}


def main() -> None:
    out, count = sys.argv[1], int(sys.argv[2])
    cases = [case() for _ in range(count)]
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(cases, handle, ensure_ascii=False, indent=0)
        handle.write("\n")


if __name__ == "__main__":
    main()
