# jarvas/cli.py
"""Jarvas — ponto de entrada do assistente de IA distribuído."""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="jarvas",
        description="Jarvas — seu assistente de IA distribuído",
    )
    parser.add_argument("query", nargs="?", help="Pergunta direta (opcional)")
    parser.add_argument("--version", action="version", version="jarvas 0.1.0")
    args = parser.parse_args()

    if args.query:
        print(f"[jarvas] modo direto: {args.query}")
    else:
        print("[jarvas] modo interativo — em breve")
        sys.exit(0)


if __name__ == "__main__":
    main()
