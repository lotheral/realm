"""Reusable SeedEvent scenarios for what-if simulations.

Each function returns a tuple of SeedEvent instances suitable for passing as
`BranchSpec.initial_events` in a butterfly comparison. Kept in the realm
package (not in scripts/) so multiple scripts and validity studies can
share the exact same news payload for apples-to-apples comparisons.
"""

from __future__ import annotations

from datetime import UTC, datetime

from realm.ingestion.interfaces import SeedEvent


def build_tech_scenario() -> tuple[SeedEvent, ...]:
    """Sustained cascade of high-virality TECH news events.

    Five headlines per tick for the first 4 ticks — a realistic tech news cycle
    with launch-day frenzy followed by think-pieces, developer reactions,
    ecosystem updates, and market coverage.
    """
    t0 = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)
    headlines = [
        "Apple announces revolutionary AI device — the Apple Intelligence Core",
        "Tech giants scramble to respond to Apple AI device launch",
        "OpenAI CEO calls Apple Intelligence Core 'industry-defining moment'",
        "Semiconductor stocks surge on Apple AI device demand forecast",
        "Developers rush to build apps for Apple Intelligence Core platform",
        "Apple Intelligence Core sells out globally in 6 hours",
        "Google and Microsoft unveil AI wearable prototypes overnight",
        "Wall Street analysts double Apple price targets after AI device debut",
        "Top tech publications hail 'the iPhone moment for AI'",
        "Chipmakers report unprecedented order volumes from Apple",
        "AI developer conference sees registrations triple in a week",
        "Regulators announce review of Apple AI device privacy model",
        "Competitors rushing to match Apple AI chip specs",
        "Retail stores report record foot traffic for tech demos",
        "Startups pivot to build on Apple Intelligence Core SDK",
        "Tech layoffs pause as AI hardware boom reshapes hiring",
        "University enrollment in AI programs projected to double",
        "Tech billionaires line up to invest in Apple ecosystem",
        "Developer Twitter dominated by Apple AI hacks and demos",
        "Tech news dominates the entire morning cycle",
    ]
    events = []
    for i, head in enumerate(headlines):
        events.append(SeedEvent(
            event_id=f"tech-{i:03d}",
            source="scenario:tech_apple_ai",
            timestamp=t0,
            headline=head,
            body=f"Continued coverage of the Apple AI device launch — day {i // 5 + 1}.",
            topic="tech",
            sentiment=0.8,
            virality=4.0,
            entities=("Apple", "OpenAI", "Tim Cook", "Google", "Microsoft"),
            geography=None,   # global news
        ))
    return tuple(events)
