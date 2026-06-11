# Public alpha tester guide

This alpha is for testing Monolith as a local AI workbench.

## What to test first

1. Install dependencies
2. Initialize database
3. Start Monolith
4. Open `/models`
5. Download or scan a local GGUF
6. Create a chat profile
7. Open `/chat`
8. Run a short test prompt

## Suggested smoke prompt

    Hello. In one short paragraph, say what model you are and what you can help with.

The exact model answer may vary.

## Things worth reporting

- install failure
- missing dependency
- broken route
- failed model download
- model appears in inventory but not chat
- chat profile launches wrong binary
- confusing config behavior
- UI button does nothing
- error messages that do not explain the problem

## Known alpha limitations

- llama.cpp must be installed separately
- model quality depends on the selected GGUF and flags
- generated profiles have conservative defaults
- profile editing UI is not complete yet
- Docker is not the recommended alpha path
- local prompt UI is not complete yet
