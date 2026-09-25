# content-repurpose-pack

This skill turns a raw content seed into a publish-ready pack in the Testing Academy voice: Medium article, LinkedIn post, LinkedIn image prompts, and Medium cover prompt.

## Objective

Take any seed type and return a clean production pack without inventing unsupported claims.

Allowed seed inputs:
- bare title
- rough bullets or steps
- screenshot
- URL
- article or thread
- spoken brain dump

## Operating rules

1. Load the voice before writing.
   - Read the brand voice reference.
   - Read the deliverable specs.
   - Read the worked example.
2. No em dashes anywhere.
3. Do not pad with filler to hit a count.
4. If the title says seven steps and the bullets say five, title wins.
5. Split compound bullets at natural seams.
6. Mine exactly five things from the seed:
   - transferable thesis
   - framework
   - verbatim assets
   - numbers
   - discard pile of original CTAs
7. Only call a number factual if it is owned, verifiable, or clearly attributed.
8. Prefer a real receipt or a composite flagged as anonymized.
9. Keep one offer tier per post.
10. Run a closing sweep before publishing.

## Pipeline

1. Identify seed shape.
2. Reconcile promised number.
3. Mine five things.
4. Map to a content thread.
5. Write four deliverables.
6. Add controversial hooks only if asked.
7. Run closing sweep.

## Voice spine

Use the same three-beat structure for every article or post:
- Hook: create a gap and earn the expand
- Story: pay it off with one real receipt
- Offer: convert attention into one next action

LinkedIn target length: 220 to 260 words. Medium target length: 2,500 to 3,200 words.

## Banned phrases

Avoid common filler phrases and inflated language such as:
- game-changer
- leverage
- revolutionary
- unlock the power of
- lightning-fast
- next-level
- groundbreaking
- proven framework (unless attributed)

## Thread selection

Before writing, name one of the content threads:
- The Math Doesn't Work
- AI Tests AI
- Pattern Recognition
- Quality Gates
- Speed
- Infrastructure
- Stability
- Deep Debugging
- Migration, Selenium to Playwright
- Career Stakes
- Foundation repo
- Learning Path, 90 Days
- Workflow, ICSR in practice

## Deliverables

Return four separate files:
1. `pack-1-medium-article.md`
2. `pack-2-linkedin-post.md`
3. `pack-3-linkedin-image-prompts.md`
4. `pack-4-medium-image-prompt.md`

Each output should be stand-alone and not merged with the others.

## Link first comment pattern

For a link-based offer:
- mention the asset in the body
- include the URL in the first comment
- keep the offer one-tier and specific

## Closing sweep checklist

Run every time:
- grep for em dashes; must be zero
- grep for banned phrases; must be zero or intentionally contextualized
- count words
- run Chai test: colleague or brand?
- run BFSI CTO test: nod or wince?
- run next-sprint test: usable or clickbait?

## Output format

When asked for a full pack, emit files in a structured order:
1. Medium article
2. LinkedIn post
3. LinkedIn image prompts
4. Medium cover prompt

If asked for a single artifact, only return that artifact.
