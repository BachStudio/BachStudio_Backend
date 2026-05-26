from fastapi import APIRouter, HTTPException, Response, status

from app.schemas.project import ProjectData
from app.services import project as project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("/", response_model=ProjectData, status_code=status.HTTP_200_OK)
def save_project(payload: ProjectData) -> ProjectData:
	return project_service.save_project(payload)


@router.get("/", response_model=list[ProjectData])
def list_projects() -> list[ProjectData]:
	return project_service.list_projects()


@router.get("/{project_name:path}", response_model=ProjectData)
def load_project(project_name: str) -> ProjectData:
	try:
		return project_service.load_project(project_name)
	except project_service.ProjectNotFoundError as exc:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found") from exc


@router.delete("/{project_name:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_name: str) -> Response:
	project_service.delete_project(project_name)
	return Response(status_code=status.HTTP_204_NO_CONTENT)
