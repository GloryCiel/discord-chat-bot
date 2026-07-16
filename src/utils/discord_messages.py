"""Helpers for Discord message limits."""


def split_message(message: str, limit: int = 1900) -> list[str]:
    if not message:
        return [""]
    return [message[index : index + limit] for index in range(0, len(message), limit)]
