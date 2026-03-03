"""
Agent Framework — lightweight agentic loop using Claude's tool_use capability.

Provides AgentTool and AgentRunner for building autonomous AI agents that can
use tools (Firecrawl, web search, etc.) to accomplish tasks.
"""
import json
import logging
import threading
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger(__name__)

# Safety limit on agentic iterations
MAX_ITERATIONS = 15

# Default model for agent reasoning
AGENT_MODEL = 'claude-sonnet-4-20250514'


@dataclass
class AgentTool:
    """Defines a tool available to an agent."""
    name: str
    description: str
    input_schema: dict
    executor: callable  # function(params) -> str

    def to_api_schema(self):
        return {
            'name': self.name,
            'description': self.description,
            'input_schema': self.input_schema,
        }


@dataclass
class AgentResult:
    """Result of an agent execution."""
    success: bool
    output: str  # Final text output from the agent
    tool_results: dict = field(default_factory=dict)  # Accumulated tool outputs keyed by tool name
    execution_log: list = field(default_factory=list)  # Step-by-step log
    input_tokens: int = 0
    output_tokens: int = 0
    iterations: int = 0
    error: str = None


class AgentRunner:
    """
    Runs a Claude-powered agentic loop.

    The agent receives a system prompt and user message, then autonomously
    decides which tools to call. The loop continues until the agent produces
    a final text response (no tool calls) or hits the iteration limit.
    """

    def __init__(self, tools, system_prompt, cancel_event=None):
        """
        Args:
            tools: List of AgentTool instances.
            system_prompt: System prompt defining the agent's role and goals.
            cancel_event: Optional threading.Event to signal cancellation.
        """
        self.tools = {t.name: t for t in tools}
        self.system_prompt = system_prompt
        self.cancel_event = cancel_event or threading.Event()

        from app.models.settings import Settings
        from config import Config
        api_key = Settings.get('anthropic_api_key') or Config.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError('Anthropic API key not configured')
        self.client = anthropic.Anthropic(api_key=api_key)

    def run(self, user_message, max_iterations=None):
        """
        Execute the agentic loop.

        Args:
            user_message: The task/prompt for the agent.
            max_iterations: Override the default iteration limit.

        Returns:
            AgentResult with the execution results.
        """
        limit = max_iterations or MAX_ITERATIONS
        messages = [{'role': 'user', 'content': user_message}]
        api_tools = [t.to_api_schema() for t in self.tools.values()]

        result = AgentResult(success=False, output='')
        tool_results = {}

        for iteration in range(limit):
            # Check for cancellation
            if self.cancel_event.is_set():
                result.error = 'Cancelled'
                result.execution_log.append({
                    'iteration': iteration + 1,
                    'action': 'cancelled',
                })
                return result

            result.iterations = iteration + 1

            try:
                response = self.client.messages.create(
                    model=AGENT_MODEL,
                    max_tokens=4096,
                    system=self.system_prompt,
                    tools=api_tools,
                    messages=messages,
                )
            except Exception as e:
                logger.error(f'Agent API call failed on iteration {iteration + 1}: {e}')
                result.error = str(e)
                result.execution_log.append({
                    'iteration': iteration + 1,
                    'action': 'api_error',
                    'error': str(e),
                })
                return result

            # Track token usage
            if hasattr(response, 'usage'):
                result.input_tokens += response.usage.input_tokens
                result.output_tokens += response.usage.output_tokens

            # Process response content blocks
            has_tool_use = False
            text_output = ''
            tool_use_blocks = []

            for block in response.content:
                if block.type == 'text':
                    text_output += block.text
                elif block.type == 'tool_use':
                    has_tool_use = True
                    tool_use_blocks.append(block)

            # If no tool calls, we're done — agent produced final output
            if not has_tool_use:
                result.success = True
                result.output = text_output
                result.tool_results = tool_results
                result.execution_log.append({
                    'iteration': iteration + 1,
                    'action': 'final_response',
                    'output_preview': text_output[:200],
                })
                return result

            # Execute tool calls and build tool results
            messages.append({'role': 'assistant', 'content': response.content})

            tool_result_blocks = []
            for block in tool_use_blocks:
                tool_name = block.name
                tool_input = block.input

                log_entry = {
                    'iteration': iteration + 1,
                    'action': 'tool_call',
                    'tool': tool_name,
                    'input_preview': json.dumps(tool_input)[:200],
                }

                tool = self.tools.get(tool_name)
                if not tool:
                    tool_output = f'Error: Unknown tool "{tool_name}"'
                    log_entry['error'] = tool_output
                else:
                    try:
                        tool_output = tool.executor(tool_input)
                        # Accumulate results by tool name
                        if tool_name not in tool_results:
                            tool_results[tool_name] = []
                        tool_results[tool_name].append({
                            'input': tool_input,
                            'output_preview': str(tool_output)[:500],
                        })
                        log_entry['success'] = True
                    except Exception as e:
                        tool_output = f'Error executing {tool_name}: {e}'
                        log_entry['error'] = str(e)
                        logger.warning(f'Agent tool {tool_name} failed: {e}')

                # Truncate very long tool outputs to stay within context limits
                if isinstance(tool_output, str) and len(tool_output) > 15000:
                    tool_output = tool_output[:15000] + '\n\n[...output truncated]'

                tool_result_blocks.append({
                    'type': 'tool_result',
                    'tool_use_id': block.id,
                    'content': str(tool_output),
                })
                result.execution_log.append(log_entry)

            messages.append({'role': 'user', 'content': tool_result_blocks})

        # Hit iteration limit
        result.error = f'Reached maximum iterations ({limit})'
        result.output = text_output  # Return whatever text was last generated
        result.tool_results = tool_results
        result.execution_log.append({
            'iteration': limit,
            'action': 'max_iterations_reached',
        })
        return result
