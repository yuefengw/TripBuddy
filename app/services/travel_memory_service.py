"""Persistent local memory and session storage for the travel agent."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any, Dict, List, Optional

from loguru import logger

from app.models.travel import IntentRouteResult, SessionHistoryEntry, TripContextMemory, UserProfileMemory
from app.services.travel_utils import (
    extract_budget_amount,
    extract_companions,
    extract_destination,
    extract_duration_days,
    extract_interests,
    extract_month,
    extract_origin,
    extract_preference_notes,
    unique_strings,
)


class TravelMemoryService:
    """Simple JSON-backed long-term and trip memory store."""

    def __init__(self, store_path: str = "app/data/travel_memory.json") -> None:
        self.store_path = Path(store_path)
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        if not self.store_path.exists():
            self._write_store({"profiles": {}, "trips": {}, "sessions": {}})

    def _read_store(self) -> Dict[str, Any]:
        with self._lock:
            try:
                return json.loads(self.store_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning(f"Failed to read travel memory store, recreating it: {exc}")
                data = {"profiles": {}, "trips": {}, "sessions": {}}
                self._write_store(data)
                return data

    def _write_store(self, data: Dict[str, Any]) -> None:
        with self._lock:
            self.store_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def get_user_profile(self, session_id: str) -> UserProfileMemory:
        profile = self._read_store().get("profiles", {}).get(session_id, {})
        return UserProfileMemory(**profile)

    def get_trip_context(self, session_id: str) -> TripContextMemory:
        trip_context = self._read_store().get("trips", {}).get(session_id, {})
        return TripContextMemory(**trip_context)

    def get_session_history(self, session_id: str) -> List[Dict[str, str]]:
        return self._read_store().get("sessions", {}).get(session_id, [])

    def upsert_user_profile(
        self, session_id: str, profile: UserProfileMemory | Dict[str, Any]
    ) -> UserProfileMemory:
        model = profile if isinstance(profile, UserProfileMemory) else UserProfileMemory(**profile)
        data = self._read_store()
        data.setdefault("profiles", {})[session_id] = model.model_dump()
        self._write_store(data)
        return model

    def upsert_trip_context(
        self, session_id: str, trip_context: TripContextMemory | Dict[str, Any]
    ) -> TripContextMemory:
        model = trip_context if isinstance(trip_context, TripContextMemory) else TripContextMemory(**trip_context)
        data = self._read_store()
        data.setdefault("trips", {})[session_id] = model.model_dump()
        self._write_store(data)
        return model

    def merge_memories(
        self,
        session_id: str,
        user_profile: Optional[Dict[str, Any]] = None,
        trip_context: Optional[Dict[str, Any]] = None,
    ) -> tuple[UserProfileMemory, TripContextMemory]:
        current_profile = self.get_user_profile(session_id)
        current_trip = self.get_trip_context(session_id)

        if user_profile:
            current_profile = self.upsert_user_profile(
                session_id,
                current_profile.model_copy(
                    update=self._merge_dicts(current_profile.model_dump(), user_profile)
                ),
            )

        if trip_context:
            current_trip = self.upsert_trip_context(
                session_id,
                current_trip.model_copy(
                    update=self._merge_dicts(current_trip.model_dump(), trip_context)
                ),
            )

        return current_profile, current_trip

    def learn_from_question(
        self, session_id: str, question: str
    ) -> tuple[UserProfileMemory, TripContextMemory]:
        profile = self.get_user_profile(session_id)
        trip_context = self.get_trip_context(session_id)

        budget_amount = extract_budget_amount(question)
        duration_days = extract_duration_days(question)
        destination = extract_destination(question)
        origin = extract_origin(question)
        travel_month = extract_month(question)
        interests = extract_interests(question)
        companions = extract_companions(question)
        notes = extract_preference_notes(question)

        if budget_amount:
            profile.budget_preference = f"{budget_amount}元左右"
            trip_context.budget_amount = budget_amount

        if "慢节奏" in question or "不想太赶" in question:
            profile.pace_preference = "慢节奏"
            profile.travel_style = unique_strings([*profile.travel_style, "休闲"])
        if "自由行" in question:
            profile.travel_style = unique_strings([*profile.travel_style, "自由行"])
        if "住市中心" in question:
            profile.accommodation_preference = "市中心"
        if "不吃辣" in question:
            profile.dietary_preferences = unique_strings([*profile.dietary_preferences, "不吃辣"])

        if notes:
            profile.notes = unique_strings([*profile.notes, *notes])
        if companions:
            profile.companion_preference = unique_strings([*profile.companion_preference, *companions])
            trip_context.companions = unique_strings([*trip_context.companions, *companions])
        if interests:
            trip_context.interests = unique_strings([*trip_context.interests, *interests])
        if destination:
            trip_context.destination = destination
            profile.preferred_destinations = unique_strings([*profile.preferred_destinations, destination])
        if origin:
            trip_context.origin = origin
        if travel_month:
            trip_context.travel_month = travel_month
        if duration_days:
            trip_context.duration_days = duration_days

        self.upsert_user_profile(session_id, profile)
        self.upsert_trip_context(session_id, trip_context)
        return profile, trip_context

    def append_turn(
        self, session_id: str, question: str, answer: str, route: IntentRouteResult
    ) -> None:
        data = self._read_store()
        session_entries = data.setdefault("sessions", {}).setdefault(session_id, [])

        for role, content in (("user", question), ("assistant", answer)):
            entry = SessionHistoryEntry(
                role=role,
                content=content,
                timestamp=datetime.utcnow().isoformat(),
                route_type=route.route_type,
                intent=route.intent,
            )
            session_entries.append(entry.model_dump())

        self._write_store(data)

    def remember_trip_output(self, session_id: str, answer: str, route: IntentRouteResult) -> None:
        if route.selected_workflow not in {
            "itinerary_generation_workflow",
            "destination_recommendation_workflow",
            "travel_checklist_workflow",
        } and route.route_type != "plan_execute":
            return

        trip_context = self.get_trip_context(session_id)
        trip_context.current_plan = answer[:2000]
        if route.route_type == "plan_execute":
            trip_context.constraints = unique_strings([*trip_context.constraints, "行中重规划"])
        self.upsert_trip_context(session_id, trip_context)

    def clear_session(self, session_id: str) -> bool:
        data = self._read_store()
        removed = False
        if session_id in data.get("sessions", {}):
            del data["sessions"][session_id]
            removed = True
        if session_id in data.get("trips", {}):
            del data["trips"][session_id]
            removed = True
        self._write_store(data)
        return removed

    @staticmethod
    def _merge_dicts(base: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(base)
        for key, value in updates.items():
            if value is None:
                continue
            if isinstance(value, list):
                merged[key] = unique_strings([*(merged.get(key) or []), *value])
            else:
                merged[key] = value
        return merged


travel_memory_service = TravelMemoryService()
