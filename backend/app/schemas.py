
from typing import Literal

from pydantic import BaseModel, Field, model_validator


# ==================================================
# SUBJECTS
# ==================================================

Subject = Literal[
    # Primary and middle school
    "English",
    "Mathematics",
    "EVS",
    "Hindi",

    # General school subjects
    "Science",
    "Social Science",
    "Computer Science",

    # Higher secondary
    "Physics",
    "Chemistry",
    "Biology",
    "Accountancy",
    "Economics",
    "Business Studies",
    "History",
    "Geography",
    "Political Science",

    # College - B.Sc.
    "Botany",
    "Zoology",

    # College - B.A.
    "Sociology",
    "Psychology",

    # College - Commerce
    "Finance",

    # College - Engineering and Technology
    "Programming",
    "Data Structures",
    "Engineering Mathematics",
    "Electronics",

    # College - Computer Applications
    "Database Management",
    "Computer Networks",

    # College - Management
    "Management",
    "Marketing",

    # College - Pharmacy
    "Pharmaceutics",
    "Pharmacology",
    "Pharmaceutical Chemistry",
    "Pharmacognosy",

    "General Studies",

    # Coding mode
    "coding",
]


# ==================================================
# EDUCATION LEVEL
# ==================================================

EducationLevel = Literal[
    "primary",
    "middle",
    "secondary",
    "higher_secondary",
    "college",
]


# ==================================================
# COLLEGE DEGREES
# ==================================================

Degree = Literal[
    "B.A.",
    "B.Sc.",
    "B.Com.",
    "B.Tech.",
    "B.E.",
    "BCA",
    "BBA",
    "B.Pharm.",
    "Other",
]


# ==================================================
# STUDY MODE
# ==================================================

Mode = Literal[
    "auto",
    "offline",
    "online",
]


# ==================================================
# ANSWER ORIGIN
# ==================================================

AnswerOrigin = Literal[
    "model",
    "notes",
    "web",
    "mixed",
    "fallback",
]


# ==================================================
# ASK REQUEST
# ==================================================

class AskRequest(BaseModel):

    question: str = Field(
        min_length=1,
        max_length=1000,
    )

    conversation_id: int | None = Field(
        default=None,
        gt=0,
    )

    attachment_ids: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    student_id: str = Field(
        default="demo-student",
        min_length=1,
        max_length=80,
    )

    # Education information

    education_level: EducationLevel = "secondary"

    class_level: int | None = Field(
        default=None,
        ge=1,
        le=12,
    )

    degree: Degree | None = None

    study_year: int | None = Field(
        default=None,
        ge=1,
        le=6,
    )

    # Academic subject

    subject: Subject | None = None

    # Language

    language: Literal[
        "auto",
        "en",
        "hi",
    ] = "auto"

    # Answer settings

    simplify: bool = False

    coding_mode: bool = False

    mode: Mode = "auto"

    # ==================================================
    # VALIDATE EDUCATION DETAILS
    # ==================================================

    @model_validator(mode="after")
    def validate_education_details(self):

        school_levels = {
            "primary": range(1, 6),
            "middle": range(6, 9),
            "secondary": range(9, 11),
            "higher_secondary": range(11, 13),
        }

        # ----------------------------------------------
        # COLLEGE VALIDATION
        # ----------------------------------------------

        if self.education_level == "college":

            if self.class_level is not None:

                raise ValueError(
                    "College requests must not include class_level."
                )

            if not self.degree:

                raise ValueError(
                    "Please select a college degree."
                )

            if self.study_year is None:

                raise ValueError(
                    "Please select your college year."
                )

        # ----------------------------------------------
        # SCHOOL VALIDATION
        # ----------------------------------------------

        else:

            if self.degree is not None:

                raise ValueError(
                    "Degree is only available for college students."
                )

            if self.study_year is not None:

                raise ValueError(
                    "Study year is only available for college students."
                )

            if self.class_level is not None:

                allowed_classes = school_levels[
                    self.education_level
                ]

                if self.class_level not in allowed_classes:

                    raise ValueError(
                        "The selected class does not match "
                        "the education level."
                    )

        # ----------------------------------------------
        # COMMERCE SUBJECT VALIDATION
        # ----------------------------------------------

        commerce_subjects = {
            "Accountancy",
            "Business Studies",
            "Finance",
        }

        if (
            self.subject in commerce_subjects
            and self.education_level not in (
                "higher_secondary",
                "college",
            )
        ):

            raise ValueError(
                "This subject is available for "
                "Higher Secondary and College students."
            )

        # ----------------------------------------------
        # CODING VALIDATION
        # ----------------------------------------------

        if self.coding_mode and self.subject not in (
            None,
            "coding",
        ):

            raise ValueError(
                "When coding mode is enabled, "
                "subject must be coding."
            )

        return self


# ==================================================
# SOURCE MODEL
# ==================================================

class Source(BaseModel):

    id: int = 0

    kind: Literal[
        "notes",
        "web",
    ] = "notes"

    title: str

    section: str | None = None

    page: int | None = None

    url: str | None = None

    score: float | None = None

    snippet: str

    text: str = Field(
        exclude=True,
    )


# ==================================================
# ASK RESPONSE
# ==================================================

class AskResponse(BaseModel):

    answer: str

    sources: list[Source]

    confidence: float

    answered_from: AnswerOrigin

    language: Literal[
        "en",
        "hi",
    ]

    online: bool

    latency_ms: int
