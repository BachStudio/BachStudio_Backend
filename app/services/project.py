import hashlib
import json
from pathlib import Path

from app.core.config import settings
from app.schemas.project import ProjectData


BACKEND_ROOT = Path(__file__).resolve().parents[2]


class ProjectNotFoundError(FileNotFoundError):
	pass


def _storage_dir() -> Path:
	configured_path = Path(settings.PROJECT_STORAGE_DIR).expanduser()
	if not configured_path.is_absolute():
		configured_path = BACKEND_ROOT / configured_path
	configured_path.mkdir(parents=True, exist_ok=True)
	return configured_path


def _project_key(project_name: str) -> str:
	normalized_name = project_name.strip().casefold()
	return hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()


def _project_path(project_name: str) -> Path:
	return _storage_dir() / f"{_project_key(project_name)}.json"


def save_project(project: ProjectData) -> ProjectData:
	path = _project_path(project.projectName)
	tmp_path = path.with_suffix(".tmp")
	payload = project.model_dump(mode="json")

	with tmp_path.open("w", encoding="utf-8") as file:
		json.dump(payload, file, ensure_ascii=False, indent=2)
		file.write("\n")

	tmp_path.replace(path)
	return project


def load_project(project_name: str) -> ProjectData:
	path = _project_path(project_name)
	if not path.exists():
		raise ProjectNotFoundError(project_name)

	with path.open("r", encoding="utf-8") as file:
		return ProjectData.model_validate(json.load(file))


def list_projects() -> list[ProjectData]:
	projects: list[ProjectData] = []
	for path in _storage_dir().glob("*.json"):
		try:
			with path.open("r", encoding="utf-8") as file:
				projects.append(ProjectData.model_validate(json.load(file)))
		except (OSError, json.JSONDecodeError, ValueError):
			continue

	return sorted(projects, key=lambda project: project.timestamp, reverse=True)


def delete_project(project_name: str) -> bool:
	path = _project_path(project_name)
	try:
		path.unlink()
		return True
	except FileNotFoundError:
		return False
