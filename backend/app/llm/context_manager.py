"""Context Manager for Local LLM Token Budgeting.

Assembles prompts within configurable token budgets for Ollama.
Adapted from context-mode architectural patterns.
"""

from dataclasses import dataclass, field


@dataclass
class TokenBudget:
    """Token budget allocation for an LLM call."""

    system_instruction: int = 500
    request_context: int = 500
    retrieved_chunks: int = 5000
    exemption_rules: int = 500
    output_reservation: int = 1500
    safety_margin: int = 192

    @property
    def total(self) -> int:
        return (
            self.system_instruction
            + self.request_context
            + self.retrieved_chunks
            + self.exemption_rules
            + self.output_reservation
            + self.safety_margin
        )


@dataclass
class ContextBlock:
    """A block of content with its role and estimated token count."""

    role: str  # system, request, chunk, rule, instruction
    content: str
    estimated_tokens: int = 0

    def __post_init__(self) -> None:
        if self.estimated_tokens == 0:
            # Rough estimate: 1 token ~ 4 characters for English text
            self.estimated_tokens = max(1, len(self.content) // 4)


def estimate_tokens(text: str) -> int:
    """Rough token estimate: 1 token ~ 4 characters."""
    return max(1, len(text) // 4)


def assemble_context(
    system_prompt: str,
    request_context: str | None = None,
    chunks: list[str] | None = None,
    exemption_rules: list[str] | None = None,
    budget: TokenBudget | None = None,
    max_context_tokens: int | None = None,
) -> list[ContextBlock]:
    """Assemble context blocks within token budget.

    Prioritizes: system > request > top-k chunks > exemption rules.
    Chunks are added in order until budget is exhausted.
    """
    if budget is None:
        budget = TokenBudget()

    if max_context_tokens:
        # Scale budget proportionally to model context window
        scale = max_context_tokens / budget.total
        budget = TokenBudget(
            system_instruction=int(budget.system_instruction * scale),
            request_context=int(budget.request_context * scale),
            retrieved_chunks=int(budget.retrieved_chunks * scale),
            exemption_rules=int(budget.exemption_rules * scale),
            output_reservation=int(budget.output_reservation * scale),
            safety_margin=int(budget.safety_margin * scale),
        )

    blocks: list[ContextBlock] = []
    tokens_used = 0

    # 1. System instruction (always included)
    sys_block = ContextBlock("system", system_prompt)
    if sys_block.estimated_tokens <= budget.system_instruction:
        blocks.append(sys_block)
        tokens_used += sys_block.estimated_tokens

    # 2. Request context
    if request_context:
        req_block = ContextBlock("request", request_context)
        if req_block.estimated_tokens <= budget.request_context:
            blocks.append(req_block)
            tokens_used += req_block.estimated_tokens

    # 3. Retrieved chunks (top-k that fit)
    if chunks:
        chunk_budget = budget.retrieved_chunks
        for chunk_text in chunks:
            block = ContextBlock("chunk", chunk_text)
            if block.estimated_tokens <= chunk_budget:
                blocks.append(block)
                chunk_budget -= block.estimated_tokens
                tokens_used += block.estimated_tokens
            else:
                break  # Budget exhausted

    # 4. Exemption rules
    if exemption_rules:
        rule_budget = budget.exemption_rules
        for rule_text in exemption_rules:
            block = ContextBlock("rule", rule_text)
            if block.estimated_tokens <= rule_budget:
                blocks.append(block)
                rule_budget -= block.estimated_tokens
                tokens_used += block.estimated_tokens

    return blocks


def blocks_to_prompt(blocks: list[ContextBlock]) -> str:
    """Convert context blocks to a single prompt string."""
    sections = []
    for block in blocks:
        if block.role == "system":
            sections.append(block.content)
        elif block.role == "request":
            sections.append(f"\n--- Request Context ---\n{block.content}")
        elif block.role == "chunk":
            sections.append(f"\n--- Document Excerpt ---\n{block.content}")
        elif block.role == "rule":
            sections.append(f"\n--- Exemption Rule ---\n{block.content}")
    return "\n".join(sections)
