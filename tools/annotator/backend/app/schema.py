"""
Label schema v1 and validation rules for Cricket Delivery Annotator.
Can be imported by backend API and eval/score.py.
"""

from __future__ import annotations

from typing import List, Literal, Optional, Any, Dict
from pydantic import BaseModel, Field, model_validator, ValidationInfo

from app.calib_constants import CALIB_ERROR_PX, CALIB_POINT_NAMES
from app.calib import validate_calibration_geometry


BallColour = Literal["white", "red", "pink"]
BatterHand = Literal["right", "left"]
BowlerType = Literal["pace", "spin"]
Lighting = Literal["bright", "overcast", "low"]
ImpactType = Literal["bat", "pad", "stumps", "none"]
LBWDecision = Literal[
    "out",
    "not_out_pitched_leg",
    "not_out_impact_outside",
    "not_out_missing",
    "umpires_call",
]
LabelFlag = Literal["ball_not_visible", "camera_moved", "bad_calibration", "unclear"]
LabelStatus = Literal["draft", "final", "flagged"]
LabelMode = Literal["assisted", "blind"]
SplitType = Literal["dev", "final"]
CalibrationSource = Literal["system_verified", "system_adjusted", "manual"]


class Point(BaseModel):
    frame: int
    x: float
    y: float


class ImpactPoint(BaseModel):
    type: ImpactType
    frame: Optional[int] = None
    x: Optional[float] = None
    y: Optional[float] = None

    @model_validator(mode="after")
    def validate_impact(self) -> "ImpactPoint":
        if self.type == "none":
            if self.frame is not None or self.x is not None or self.y is not None:
                raise ValueError("When impact.type is 'none', frame, x, and y must all be null.")
        return self


class CalibrationGT(BaseModel):
    points: Dict[str, List[float]]
    source: CalibrationSource
    residual_px: Optional[float] = None
    updated_at: str

    @model_validator(mode="after")
    def validate_calib_gt(self) -> "CalibrationGT":
        missing = [k for k in CALIB_POINT_NAMES if k not in self.points]
        if missing:
            raise ValueError(f"calibration_gt missing points: {missing}")
        for k, pt in self.points.items():
            if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
                raise ValueError(f"calibration_gt point {k} must have [x, y] coordinates, got {pt}")
        return self


class Label(BaseModel):
    schema_version: int = Field(default=1)
    clip_id: str
    split: Optional[SplitType] = None
    annotator: str
    mode: LabelMode
    status: LabelStatus
    created_at: str
    updated_at: str
    ball_colour: Optional[BallColour] = None
    batter_hand: Optional[BatterHand] = None
    bowler_type: Optional[BowlerType] = None
    lighting: Optional[Lighting] = None
    release: Optional[Point] = None
    bounce: Optional[Point] = None
    impact: Optional[ImpactPoint] = None
    last_visible_frame: Optional[int] = None
    lbw: Optional[LBWDecision] = None
    calibration_gt: Optional[CalibrationGT] = None
    flags: List[LabelFlag] = Field(default_factory=list)
    notes: str = ""

    @model_validator(mode="after")
    def validate_rules(self, info: ValidationInfo) -> "Label":
        context = info.context or {}
        frame_count = context.get("frame_count")
        width = context.get("width")
        height = context.get("height")

        # 1. schema_version must be 1
        if self.schema_version != 1:
            raise ValueError("schema_version must be 1")

        # 2. Impact type none check
        if self.impact is not None and self.impact.type == "none":
            if (
                self.impact.frame is not None
                or self.impact.x is not None
                or self.impact.y is not None
            ):
                raise ValueError("When impact.type is 'none', frame, x, and y must be null")

        # 3. LBW rule: lbw may be non-null only when impact.type == 'pad'
        if self.lbw is not None:
            if self.impact is None or self.impact.type != "pad":
                raise ValueError(
                    f"lbw may be non-null only when impact.type == 'pad', got impact={self.impact}"
                )

        # 4. Frame order checks
        # release.frame < bounce.frame
        if self.release is not None and self.bounce is not None:
            if self.release.frame >= self.bounce.frame:
                raise ValueError(
                    f"release.frame ({self.release.frame}) must be strictly less than bounce.frame ({self.bounce.frame})"
                )

        # bounce.frame <= impact.frame when impact exists and has a frame
        if (
            self.bounce is not None
            and self.impact is not None
            and self.impact.frame is not None
        ):
            if self.bounce.frame > self.impact.frame:
                raise ValueError(
                    f"bounce.frame ({self.bounce.frame}) must be <= impact.frame ({self.impact.frame})"
                )

        # impact.frame <= last_visible_frame when impact exists and has a frame
        if (
            self.impact is not None
            and self.impact.frame is not None
            and self.last_visible_frame is not None
        ):
            if self.impact.frame > self.last_visible_frame:
                raise ValueError(
                    f"impact.frame ({self.impact.frame}) must be <= last_visible_frame ({self.last_visible_frame})"
                )

        # bounce.frame <= last_visible_frame when bounce and last_visible_frame exist
        if self.bounce is not None and self.last_visible_frame is not None:
            if self.bounce.frame > self.last_visible_frame:
                raise ValueError(
                    f"bounce.frame ({self.bounce.frame}) must be <= last_visible_frame ({self.last_visible_frame})"
                )

        # release.frame <= last_visible_frame when release and last_visible_frame exist
        if self.release is not None and self.last_visible_frame is not None:
            if self.release.frame > self.last_visible_frame:
                raise ValueError(
                    f"release.frame ({self.release.frame}) must be <= last_visible_frame ({self.last_visible_frame})"
                )

        # 5. Calibration geometry validation (if calibration_gt is present)
        if self.calibration_gt is not None:
            geom_errors = validate_calibration_geometry(
                self.calibration_gt.points,
                width=width,
                height=height,
            )
            if geom_errors:
                raise ValueError("; ".join(geom_errors))

            if (
                self.calibration_gt.residual_px is not None
                and self.calibration_gt.residual_px > CALIB_ERROR_PX
                and "bad_calibration" not in self.flags
            ):
                raise ValueError(
                    f"calibration_gt residual_px ({self.calibration_gt.residual_px:.2f} px) exceeds CALIB_ERROR_PX ({CALIB_ERROR_PX} px)"
                )

        # 6. Status final requirements
        if self.status == "final":
            if not self.annotator or not self.annotator.strip():
                raise ValueError("annotator is required for status 'final'")
            if self.release is None:
                raise ValueError("release is required for status 'final'")
            if self.bounce is None:
                raise ValueError("bounce is required for status 'final'")
            if self.impact is None:
                raise ValueError("impact is required for status 'final'")
            if self.impact.type != "none":
                if (
                    self.impact.frame is None
                    or self.impact.x is None
                    or self.impact.y is None
                ):
                    raise ValueError(
                        f"impact frame, x, and y are required when impact.type is '{self.impact.type}' in status 'final'"
                    )
            if self.last_visible_frame is None:
                raise ValueError("last_visible_frame is required for status 'final'")
            if self.ball_colour is None:
                raise ValueError("ball_colour is required for status 'final'")
            if self.batter_hand is None:
                raise ValueError("batter_hand is required for status 'final'")
            if self.calibration_gt is None:
                raise ValueError("calibration_gt is required for status 'final'")
            if self.split is None:
                raise ValueError("split is required for status 'final'")
            if self.bowler_type is None:
                raise ValueError("bowler_type is required for status 'final'")
            if self.lighting is None:
                raise ValueError("lighting is required for status 'final'")
            if self.impact.type == "pad" and self.lbw is None:
                raise ValueError("lbw is required for status 'final' when impact.type is 'pad'")

        # 7. Dimensional bounds validation if context is provided
        if frame_count is not None or width is not None or height is not None:
            self._validate_bounds(frame_count=frame_count, width=width, height=height)

        return self

    def _validate_bounds(
        self,
        frame_count: Optional[int] = None,
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> None:
        def check_frame(f: int, name: str) -> None:
            if frame_count is not None:
                if not (0 <= f < frame_count):
                    raise ValueError(
                        f"{name} frame {f} out of bounds [0, {frame_count - 1}]"
                    )

        def check_xy(x: float, y: float, name: str) -> None:
            if width is not None:
                if not (0.0 <= x <= float(width)):
                    raise ValueError(
                        f"{name} x coordinate {x} out of bounds [0, {width}]"
                    )
            if height is not None:
                if not (0.0 <= y <= float(height)):
                    raise ValueError(
                        f"{name} y coordinate {y} out of bounds [0, {height}]"
                    )

        if self.release is not None:
            check_frame(self.release.frame, "release")
            check_xy(self.release.x, self.release.y, "release")

        if self.bounce is not None:
            check_frame(self.bounce.frame, "bounce")
            check_xy(self.bounce.x, self.bounce.y, "bounce")

        if self.impact is not None and self.impact.frame is not None:
            check_frame(self.impact.frame, "impact")
            if self.impact.x is not None and self.impact.y is not None:
                check_xy(self.impact.x, self.impact.y, "impact")

        if self.last_visible_frame is not None:
            check_frame(self.last_visible_frame, "last_visible_frame")


def validate_label(
    data: Any,
    frame_count: Optional[int] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
) -> Label:
    """Validate raw dict or model against Label schema and clip dimensions."""
    context: Dict[str, Any] = {}
    if frame_count is not None:
        context["frame_count"] = frame_count
    if width is not None:
        context["width"] = width
    if height is not None:
        context["height"] = height

    if isinstance(data, Label):
        data._validate_bounds(frame_count=frame_count, width=width, height=height)
        return data

    if isinstance(data, dict):
        return Label.model_validate(data, context=context)

    raise TypeError(f"Expected dict or Label, got {type(data)}")
