"""Basic input readiness checks, not licensing or OpenAPI validation."""
import json
from pathlib import Path

from .adapters import ADAPTERS

ROOT = Path(__file__).resolve().parents[2]

# "verified": a license permits redistribution (PrismHR, Apache-2.0).
# "user_approved_private_upload": the organizer approved sharing the pack
# (isolved, UKG Ready; see docs/ASSIGNMENT.md "Reference status").
ACCEPTED_DISTRIBUTION_STATUSES = ("verified", "user_approved_private_upload")


def _file_inside(base, relative, suffixes):
    """Return True when `relative` names an existing file with an allowed suffix under `base`."""
    base = base.resolve()
    path = (base / relative).resolve()
    return base in path.parents and path.suffix.lower() in suffixes and path.is_file()


def _openapi_issues(spec, base):
    issues = []
    relative = spec.get("relative_path")
    if not isinstance(relative, str) or not relative:
        issues.append("Approved OpenAPI filename is missing.")
    elif not _file_inside(base, relative, (".json", ".yaml", ".yml")):
        issues.append("Approved OpenAPI file must exist inside the provider openapi directory.")
    if not all(spec.get(key) for key in ("version", "source", "sha256")):
        issues.append("OpenAPI provenance/version/checksum metadata is incomplete.")
    return issues


def _reference_artifact_issues(artifact, base):
    """Checks for providers with no OpenAPI contract, such as UKG Ready's extracted schema bundle."""
    artifact = artifact if isinstance(artifact, dict) else {}
    issues = []
    relative = artifact.get("relative_path")
    if not isinstance(relative, str) or not relative:
        issues.append("Reference artifact filename is missing.")
    elif not _file_inside(base, relative, (".json",)):
        issues.append("Reference artifact file must exist inside the provider contract directory.")
    if not artifact.get("sha256"):
        issues.append("Reference artifact checksum is missing.")
    return issues


def load_reference(provider, root=ROOT):
    path = root / "contracts" / provider / "lookup-reference.json"
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def readiness_issues(provider, root=ROOT):
    try:
        ref = load_reference(provider, root)
        if not isinstance(ref, dict):
            return ["Lookup reference must be a JSON object."]
        issues = []
        if ref.get("provider") != provider:
            issues.append("Reference provider identifier does not match the folder.")
        if ref.get("lookup_status") != "verified":
            issues.append("Lookup contents are a template or remain unverified.")
        if not isinstance(ref.get("lookups"), list):
            issues.append("Lookup domains must be an array.")
        if not ref.get("reference_version"):
            issues.append("Reference version is missing.")
        distribution = ref.get("distribution") or {}
        if distribution.get("status") not in ACCEPTED_DISTRIBUTION_STATUSES or not distribution.get("evidence_reference"):
            issues.append("Candidate-distribution permission has not been verified.")
        spec = ref.get("openapi") or {}
        if spec.get("status") == "verified":
            issues.extend(_openapi_issues(spec, root / "contracts" / provider / "openapi"))
        elif spec.get("status") == "not_available":
            issues.extend(_reference_artifact_issues(ref.get("reference_artifact"), root / "contracts" / provider))
        else:
            issues.append("OpenAPI artifact is absent or unverified.")
        return issues
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        return ["Cannot read reference metadata: " + str(exc)]


def all_readiness_issues(root=ROOT):
    return {provider: readiness_issues(provider, root) for provider in ADAPTERS}
