"""The error hierarchy of data-model §1."""

import pytest

import tenetrag
from tenetrag import protocols
from tenetrag.protocols import errors

PARENTS = {
    "ConfigError": "TenetRAGError",
    "MissingExtraError": "ConfigError",
    "AuthError": "TenetRAGError",
    "MissingCredentialError": "AuthError",
    "CredentialSourceError": "AuthError",
    "CredentialMismatchError": "AuthError",
    "CredentialRejectedError": "AuthError",
    "StorageError": "TenetRAGError",
    "StoreUnavailableError": "StorageError",
    "UnsupportedServerError": "StorageError",
    "QueryError": "StorageError",
    "LLMError": "TenetRAGError",
    "ModelUnavailableError": "LLMError",
    "StructuredOutputError": "LLMError",
    "OutputTruncatedError": "LLMError",
    "UnsupportedRequestError": "LLMError",
    "ResponseError": "LLMError",
}
ALL_NAMES = ["TenetRAGError", *PARENTS]


def test_root_derives_from_exception_only():
    assert errors.TenetRAGError.__bases__ == (Exception,)


@pytest.mark.parametrize(("name", "parent"), PARENTS.items())
def test_direct_parent(name, parent):
    assert getattr(errors, parent) in getattr(errors, name).__bases__


def test_config_error_is_a_value_error():
    assert issubclass(errors.ConfigError, ValueError)


def test_no_unlisted_error_classes():
    defined = {
        name
        for name, value in vars(errors).items()
        if isinstance(value, type)
        and issubclass(value, BaseException)
        and value.__module__ == errors.__name__
    }
    assert defined == set(ALL_NAMES)


@pytest.mark.parametrize("name", ALL_NAMES)
def test_reexported_from_protocols_and_package(name):
    error_class = getattr(errors, name)
    assert getattr(protocols, name) is error_class
    assert getattr(tenetrag, name) is error_class
    assert name in protocols.__all__
    assert name in tenetrag.__all__


def test_structured_output_error_carries_strategy_and_attempts():
    exc = errors.StructuredOutputError(
        "Output failed schema validation", strategy="tool_call", attempts=3
    )
    assert exc.strategy == "tool_call"
    assert exc.attempts == 3
    assert str(exc) == "Output failed schema validation"


def test_missing_extra_error_names_the_extra_and_how_to_install_it():
    exc = errors.MissingExtraError("neo4j")
    assert exc.extra == "neo4j"
    assert "tenetrag[neo4j]" in str(exc)
