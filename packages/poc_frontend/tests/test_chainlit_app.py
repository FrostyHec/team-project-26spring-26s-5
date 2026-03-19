from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import poc_frontend.app as app


@pytest.mark.asyncio
async def test_on_message():
    """Test on_message handles tool execution and streaming properly."""
    # Create mock ReactAgent
    mock_agent = AsyncMock()

    async def mock_stream(msg, session_id=None):
        yield {"type": "token", "content": "I "}
        yield {"type": "tool_start", "name": "add", "input": {"a": 1, "b": 2}}
        yield {"type": "tool_end", "name": "add", "output": "3"}
        yield {"type": "token", "content": "did it."}

    mock_agent.stream = mock_stream

    # Mock chainlit elements
    mock_message_instance = AsyncMock()
    mock_step_instance = AsyncMock()
    # Chainlit steps have 'id' which we need to access
    mock_step_instance.id = "mock-id"
    # Ensure output is a generic property that we can update initially
    mock_step_instance.output = "**ReAct loop started.**\n\n"

    with patch("poc_frontend.app.cl.user_session.get", return_value=mock_agent):
        with patch("poc_frontend.app.cl.Message", return_value=mock_message_instance):
            with patch(
                "poc_frontend.app.cl.Step", return_value=mock_step_instance
            ) as step_class:
                mock_input_msg = MagicMock()
                mock_input_msg.content = "Add 1 and 2"

                await app.on_message(mock_input_msg)

                # We expect one main ReAct loop step, and another for tool call
                assert step_class.call_count == 2

                # Verify stream_token was called twice ("I ", "did it.")
                assert mock_message_instance.stream_token.call_count == 2

                # Verify message update was called once at the end
                assert mock_message_instance.update.call_count == 1
