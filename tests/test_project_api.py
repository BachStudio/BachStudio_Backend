import tempfile
import unittest

from app.core.config import settings
from app.main import app
from app.schemas.project import ProjectData
from app.services import project as project_service


class ProjectApiTest(unittest.TestCase):
	def setUp(self) -> None:
		self.original_storage_dir = settings.PROJECT_STORAGE_DIR
		self.temp_dir = tempfile.TemporaryDirectory()
		settings.PROJECT_STORAGE_DIR = self.temp_dir.name

	def tearDown(self) -> None:
		settings.PROJECT_STORAGE_DIR = self.original_storage_dir
		self.temp_dir.cleanup()

	def test_project_routes_are_registered(self) -> None:
		route_paths = {route.path for route in app.routes}

		self.assertIn("/api/v1/projects/", route_paths)
		self.assertIn("/api/v1/projects/{project_name:path}", route_paths)

	def test_save_list_load_and_delete_project(self) -> None:
		project_payload = {
			"projectName": "My Song",
			"bpm": 128,
			"tracks": [
				{
					"id": "track-1",
					"type": "instrument",
					"name": "Piano",
					"clips": [{"id": "clip-1", "start": 0, "length": 16, "notes": []}],
				}
			],
			"timestamp": 1716350000000,
		}

		project = ProjectData.model_validate(project_payload)

		saved_project = project_service.save_project(project)
		self.assertEqual(saved_project.model_dump(mode="json"), project_payload)
		self.assertEqual([item.model_dump(mode="json") for item in project_service.list_projects()], [project_payload])
		self.assertEqual(project_service.load_project("My Song").model_dump(mode="json"), project_payload)

		self.assertTrue(project_service.delete_project("My Song"))

		with self.assertRaises(project_service.ProjectNotFoundError):
			project_service.load_project("My Song")

	def test_project_name_can_use_korean_and_spaces(self) -> None:
		project_payload = {
			"projectName": "첫 번째 곡",
			"bpm": 90,
			"tracks": [],
			"timestamp": 1716350000001,
		}

		project_service.save_project(ProjectData.model_validate(project_payload))
		loaded_project = project_service.load_project("첫 번째 곡")
		self.assertEqual(loaded_project.model_dump(mode="json"), project_payload)


if __name__ == "__main__":
	unittest.main()
