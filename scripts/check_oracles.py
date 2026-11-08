#!/usr/bin/env python3
"""Report synthetic oracle matches and a separately reproduced divergence."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys


class _Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("Argumentos inválidos.")


def main(argv=None) -> int:
    try:
        parser = _Arguments(description=__doc__)
        parser.add_argument("--output", metavar="NEW", help="Salvar também em novo arquivo JSON.")
        args = parser.parse_args(argv)
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "src"))
        spec = importlib.util.spec_from_file_location("civil_development_oracle",
                                                     root / "tests" / "test_oracle.py")
        if spec is None or spec.loader is None:
            raise RuntimeError("Oráculo indisponível.")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        summary = module.check_corpus()
        output = json.dumps(summary, indent=2, ensure_ascii=True) + "\n"
        if args.output is not None:
            with open(args.output, "x", encoding="utf-8", newline="\n") as destination:
                destination.write(output)
        sys.stdout.write(output)
        sys.stdout.flush()
        return 0
    except (Exception, KeyboardInterrupt):
        sys.stderr.write("error: a verificação do oráculo não foi concluída.\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
