"""Tests for the /evaluate quiz evaluation endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from agent_core.api.dependencies import get_llm
from agent_core.api.server import create_app
from agent_core.config import AgentConfig


@pytest.fixture
def client() -> TestClient:
    """Create a test client with lifespan context."""
    config = AgentConfig(
        openai_api_key="test-key",
        model_name="gpt-4o-mini",
    )
    app = create_app(config)
    with TestClient(app) as c:
        yield c


def make_mock_llm(response_content: str) -> MagicMock:
    """Build a mock LLM that returns the given content string."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_content
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    return mock_llm


class TestEvaluateMultipleChoice:
    """multiple_choice is always auto-scored regardless of use_ai_grading."""

    def test_multiple_choice_correct(self, client: TestClient) -> None:
        """Correct answer earns full score."""
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 1,
                        "type": "multiple_choice",
                        "question": "What is 2+2?",
                        "options": ["3", "4", "5"],
                        "correct_answer": "4",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"1": "4"},
                "use_ai_grading": True,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["1"]
        assert eval_["score"] > 0
        assert eval_["standard_answer"] == "4"
        assert eval_["total_score_included"] is True

    def test_multiple_choice_wrong(self, client: TestClient) -> None:
        """Wrong answer earns zero."""
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 1,
                        "type": "multiple_choice",
                        "question": "What is 2+2?",
                        "options": ["3", "4", "5"],
                        "correct_answer": "4",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"1": "3"},
                "use_ai_grading": False,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["1"]
        assert eval_["score"] == 0.0


class TestEvaluateTrueFalse:
    """true_false is always auto-scored."""

    def test_true_false_correct(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 2,
                        "type": "true_false",
                        "question": "The earth is flat.",
                        "options": None,
                        "correct_answer": "False",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"2": "False"},
                "use_ai_grading": True,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["2"]
        assert eval_["score"] == 1.0  # default true_false score

    def test_true_false_wrong(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 2,
                        "type": "true_false",
                        "question": "The earth is flat.",
                        "options": None,
                        "correct_answer": "False",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"2": "True"},
                "use_ai_grading": True,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["2"]
        assert eval_["score"] == 0.0


class TestEvaluateFillBlankAIEnabled:
    """fill_blank with AI grading: LLM decides correct/incorrect."""

    def test_llm_returns_correct(self, client: TestClient) -> None:
        mock_llm = make_mock_llm('{"correct": true, "analysis": "Perfect!"}')
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 3,
                            "type": "fill_blank",
                            "question": "Capital of France?",
                            "options": None,
                            "correct_answer": "Paris",
                            "explanation": "It's the capital.",
                            "score": None,
                        }
                    ],
                    "user_answers": {"3": "Paris"},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["3"]
            assert eval_["score"] == 5.0  # default fill_blank score
            assert eval_["analysis"] == "Perfect!"
            assert eval_["standard_answer"] == "Paris"
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]

    def test_llm_returns_incorrect(self, client: TestClient) -> None:
        mock_llm = make_mock_llm('{"correct": false, "analysis": "Wrong."}')
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 3,
                            "type": "fill_blank",
                            "question": "Capital of France?",
                            "options": None,
                            "correct_answer": "Paris",
                            "explanation": None,
                            "score": None,
                        }
                    ],
                    "user_answers": {"3": "London"},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["3"]
            assert eval_["score"] == 0.0
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]

    def test_llm_returns_malformed_json_triggers_fallback(
        self, client: TestClient
    ) -> None:
        """Malformed LLM response falls back to exact-match scoring."""
        mock_llm = make_mock_llm("not valid json at all")
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 4,
                            "type": "fill_blank",
                            "question": "Capital of France?",
                            "options": None,
                            "correct_answer": "Paris",
                            "explanation": None,
                            "score": None,
                        }
                    ],
                    "user_answers": {"4": "Paris"},  # exact match → fallback passes
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["4"]
            assert eval_["score"] == 5.0  # exact match fallback
            assert eval_["total_score_included"] is True
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]

    def test_llm_returns_malformed_json_wrong_answer_fallback(
        self, client: TestClient
    ) -> None:
        """Malformed LLM + wrong answer → fallback scores 0."""
        mock_llm = make_mock_llm("{ invalid json")
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 4,
                            "type": "fill_blank",
                            "question": "Capital of France?",
                            "options": None,
                            "correct_answer": "Paris",
                            "explanation": None,
                            "score": None,
                        }
                    ],
                    "user_answers": {"4": "London"},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["4"]
            assert eval_["score"] == 0.0
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]

    def test_empty_user_answer_skips_llm(self, client: TestClient) -> None:
        """Empty answer → scored wrong without calling LLM."""
        mock_llm = make_mock_llm('{"correct": true}')
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 5,
                            "type": "fill_blank",
                            "question": "Capital of France?",
                            "options": None,
                            "correct_answer": "Paris",
                            "explanation": None,
                            "score": None,
                        }
                    ],
                    "user_answers": {"5": "  "},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["5"]
            assert eval_["score"] == 0.0
            mock_llm.ainvoke.assert_not_called()
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]


class TestEvaluateFillBlankAIDisabled:
    """fill_blank with AI disabled: exact-match scoring."""

    def test_exact_match_passes(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 6,
                        "type": "fill_blank",
                        "question": "Capital of France?",
                        "options": None,
                        "correct_answer": "Paris",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"6": "Paris"},
                "use_ai_grading": False,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["6"]
        assert eval_["score"] == 5.0
        assert eval_["total_score_included"] is True

    def test_trimmed_match_passes(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 6,
                        "type": "fill_blank",
                        "question": "Capital of France?",
                        "options": None,
                        "correct_answer": "Paris",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"6": "  Paris  "},
                "use_ai_grading": False,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["6"]
        assert eval_["score"] == 5.0

    def test_case_sensitive_fails(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 6,
                        "type": "fill_blank",
                        "question": "Capital of France?",
                        "options": None,
                        "correct_answer": "Paris",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"6": "paris"},
                "use_ai_grading": False,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["6"]
        assert eval_["score"] == 0.0


class TestEvaluateShortAnswerAIEnabled:
    """short_answer with AI grading: LLM returns score/standard_answer/analysis."""

    def test_llm_returns_score_and_analysis(self, client: TestClient) -> None:
        mock_llm = make_mock_llm(
            '{"score": 8.0, "standard_answer": "Paris", "analysis": "Good."}'
        )
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 7,
                            "type": "short_answer",
                            "question": "What is the capital of France?",
                            "options": None,
                            "correct_answer": "Paris",
                            "explanation": None,
                            "score": 10.0,
                        }
                    ],
                    "user_answers": {"7": "Paris"},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["7"]
            # raw_score=8/10 * max_score=10 = 8.0
            assert eval_["score"] == 8.0
            assert eval_["analysis"] == "Good."
            assert eval_["standard_answer"] == "Paris"
            assert eval_["total_score_included"] is True
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]

    def test_score_clamped_to_0_10_range(self, client: TestClient) -> None:
        mock_llm = make_mock_llm('{"score": 15.0, "standard_answer": "Paris"}')
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 8,
                            "type": "short_answer",
                            "question": "What is 2+2?",
                            "options": None,
                            "correct_answer": "4",
                            "explanation": None,
                            "score": 10.0,
                        }
                    ],
                    "user_answers": {"8": "4"},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["8"]
            # raw 15 clamped to 10, then 10/10 * 10 = 10
            assert eval_["score"] == 10.0
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]

    def test_llm_returns_malformed_json_short_answer(self, client: TestClient) -> None:
        """LLM error for short_answer triggers service_unavailable_manual fallback."""
        mock_llm = make_mock_llm("not json")
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 9,
                            "type": "short_answer",
                            "question": "Explain photosynthesis.",
                            "options": None,
                            "correct_answer": "Plants convert sunlight.",
                            "explanation": None,
                            "score": 10.0,
                        }
                    ],
                    "user_answers": {"9": "Something"},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            eval_ = response.json()["evaluations"]["9"]
            assert eval_["score"] == 0.0
            assert eval_["total_score_included"] is True
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]


class TestEvaluateShortAnswerAIDisabled:
    """short_answer with AI disabled: not scored, shown only."""

    def test_short_answer_not_scored(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 10,
                        "type": "short_answer",
                        "question": "Explain photosynthesis.",
                        "options": None,
                        "correct_answer": "Plants convert sunlight.",
                        "explanation": None,
                        "score": 10.0,
                    }
                ],
                "user_answers": {"10": "Something"},
                "use_ai_grading": False,
            },
        )
        assert response.status_code == 200
        eval_ = response.json()["evaluations"]["10"]
        assert eval_["score"] == 0.0
        assert eval_["standard_answer"] == "Plants convert sunlight."
        assert eval_["total_score_included"] is False


class TestEvaluateXLanguageHeader:
    """X-Language header is passed through to prompts."""

    def test_x_language_header_forwarded(self, client: TestClient) -> None:
        mock_llm = make_mock_llm('{"correct": true, "analysis": "OK"}')
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                headers={"X-Language": "zh"},
                json={
                    "questions": [
                        {
                            "id": 11,
                            "type": "fill_blank",
                            "question": "法国的首都是？",  # nosemgrep
                            "options": None,
                            "correct_answer": "巴黎",  # nosemgrep
                            "explanation": None,
                            "score": None,
                        }
                    ],
                    "user_answers": {"11": "巴黎"},  # nosemgrep
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            assert response.json()["evaluations"]["11"]["score"] == 5.0
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]


class TestEvaluateMixedQuestions:
    """Multiple question types in a single request are each handled correctly."""

    def test_mixed_question_types(self, client: TestClient) -> None:
        mock_llm = make_mock_llm(
            '{"correct": true, "analysis": "Good", "score": 0, "standard_answer": ""}'
        )
        client.app.dependency_overrides[  # type: ignore[attr-defined]
            get_llm
        ] = lambda: mock_llm
        try:
            response = client.post(
                "/evaluate",
                json={
                    "questions": [
                        {
                            "id": 1,
                            "type": "multiple_choice",
                            "question": "What is 2+2?",
                            "options": ["3", "4"],
                            "correct_answer": "4",
                            "explanation": None,
                            "score": None,
                        },
                        {
                            "id": 2,
                            "type": "fill_blank",
                            "question": "Capital of France?",
                            "options": None,
                            "correct_answer": "Paris",
                            "explanation": None,
                            "score": None,
                        },
                        {
                            "id": 3,
                            "type": "short_answer",
                            "question": "Explain gravity.",
                            "options": None,
                            "correct_answer": "A force.",
                            "explanation": None,
                            "score": 10.0,
                        },
                    ],
                    "user_answers": {"1": "4", "2": "Paris", "3": "Something"},
                    "use_ai_grading": True,
                },
            )
            assert response.status_code == 200
            evals = response.json()["evaluations"]
            assert "1" in evals
            assert "2" in evals
            assert "3" in evals
        finally:
            del client.app.dependency_overrides[  # type: ignore[attr-defined]
                get_llm
            ]


class TestEvaluateValidation:
    """Request validation returns 422 for malformed input."""

    def test_missing_questions_field(self, client: TestClient) -> None:
        response = client.post("/evaluate", json={"user_answers": {}})
        assert response.status_code == 422

    def test_missing_user_answers_field(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 1,
                        "type": "multiple_choice",
                        "question": "Q",
                        "options": None,
                        "correct_answer": "A",
                        "explanation": None,
                        "score": None,
                    }
                ]
            },
        )
        assert response.status_code == 422

    def test_invalid_question_type(self, client: TestClient) -> None:
        response = client.post(
            "/evaluate",
            json={
                "questions": [
                    {
                        "id": 1,
                        "type": "unknown_type",
                        "question": "Q",
                        "options": None,
                        "correct_answer": "A",
                        "explanation": None,
                        "score": None,
                    }
                ],
                "user_answers": {"1": "A"},
            },
        )
        # Pydantic validation failure
        assert response.status_code == 422
