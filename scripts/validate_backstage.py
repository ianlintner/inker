#!/usr/bin/env python3
"""Validate Backstage catalog-info.yaml file."""

import sys

import yaml


def validate_catalog(filepath: str) -> bool:
    """Validate a Backstage catalog file.

    Args:
        filepath: Path to the catalog-info.yaml file.

    Returns:
        True if valid, False otherwise.
    """
    required_fields = ["apiVersion", "kind", "metadata", "spec"]

    try:
        with open(filepath, "r") as f:
            docs = list(yaml.safe_load_all(f))
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        return False
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in {filepath}: {e}")
        return False

    valid_docs = [d for d in docs if d is not None]

    if not valid_docs:
        print("Error: No valid YAML documents found")
        return False

    for i, doc in enumerate(valid_docs):
        for field in required_fields:
            if field not in doc:
                print(f"Error in document {i}: missing required field '{field}'")
                return False

    print(f"✓ Validated {len(valid_docs)} Backstage entities")
    return True


if __name__ == "__main__":
    filepath = sys.argv[1] if len(sys.argv) > 1 else "catalog-info.yaml"
    success = validate_catalog(filepath)
    sys.exit(0 if success else 1)
