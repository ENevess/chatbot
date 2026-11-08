"""Interface de Linha de Comando (CLI) para o Chatbot de Emplacamentos (Tarefa 6 - Secao 5, 8 e 10)."""

from __future__ import annotations

import argparse
import sys

from emplacamentos_bot.bot import EmplacamentosChatbot
from emplacamentos_bot.llm.client import create_llm_client


def build_parser() -> argparse.ArgumentParser:
    """Cria o parser de argumentos da CLI."""
    parser = argparse.ArgumentParser(
        prog="emplacamentos-cli",
        description="Chatbot de Emplacamentos de Caminhões Pesados e Semi-Pesados (PoC Local).",
    )
    parser.add_argument(
        "question",
        nargs="?",
        help="Pergunta em português. Se omitida, abre o modo interativo (REPL).",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "claude"],
        default=None,
        help="Provedor de interpretação semântica ('mock' offline ou 'claude' via API Anthropic).",
    )
    parser.add_argument(
        "--show-sql",
        action="store_true",
        help="Exibe também a consulta SQL determinística gerada pela camada semântica.",
    )
    return parser


def format_cli_output(turn_result: object, show_sql: bool = False) -> str:
    """Formata a saída do turno para exibição limpa no terminal."""
    from emplacamentos_bot.bot import BotTurnResult

    assert isinstance(turn_result, BotTurnResult)
    lines = [turn_result.answer_text]
    if show_sql and turn_result.sql:
        lines.append("\n[SQL Determinístico Gerado]:")
        lines.append(turn_result.sql)
    return "\n".join(lines)


def run_cli(argv: list[str] | None = None) -> int:
    """Executa a CLI em modo pergunta única ou modo interativo."""
    parser = build_parser()
    args = parser.parse_args(argv)

    llm_client = create_llm_client(args.provider)
    bot = EmplacamentosChatbot(llm_client=llm_client)

    if args.question:
        result = bot.ask(args.question)
        print(format_cli_output(result, show_sql=args.show_sql))
        return 0

    print("======================================================================")
    print(" CHATBOT DE EMPLACAMENTOS (Caminhões Pesados e Semi-Pesados - Desde 2019)")
    print(" Digite sua pergunta em português ou 'sair' para encerrar.")
    print("======================================================================")

    while True:
        try:
            user_input = input("\nPergunta > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando o Chatbot.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("sair", "exit", "quit"):
            print("Encerrando o Chatbot.")
            break

        result = bot.ask(user_input)
        print("\n" + format_cli_output(result, show_sql=args.show_sql))

    return 0


def main() -> None:
    """Ponto de entrada do script CLI."""
    sys.exit(run_cli())


if __name__ == "__main__":
    main()
