"""Shared user definitions for the single editor account."""

from typing import Dict

EDITOR_ACCOUNT = {
	"name": "Editor",
	"email": "editor@tnf.com",
	"password": "editor@123",
}


def get_editor_account() -> Dict[str, str]:
	"""Return the configured editor identity."""
	return dict(EDITOR_ACCOUNT)


def is_editor_credentials(email: str, password: str) -> bool:
	"""Check whether the supplied credentials match the editor account."""
	return email.strip().lower() == EDITOR_ACCOUNT["email"] and password == EDITOR_ACCOUNT["password"]


def build_editor_session() -> Dict[str, str]:
	"""Build the session payload used by the frontend after editor login."""
	return {
		"name": EDITOR_ACCOUNT["name"],
		"email": EDITOR_ACCOUNT["email"],
		"role": "editor",
		"authenticated": True,
	}