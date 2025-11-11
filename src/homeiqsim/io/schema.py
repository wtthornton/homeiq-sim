from typing import Dict, Optional, Union

from pydantic import BaseModel


class EventRow(BaseModel):
  ts: int
  home_id: str
  entity_id: str
  domain: str
  state: Optional[Union[str, float, int]]
  attributes: Optional[Dict]


class RegistryRow(BaseModel):
  home_id: str
  entity_id: str
  domain: str
  device_id: Optional[str]
  name: Optional[str]
