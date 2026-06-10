# Test: Bash quoting and safety

## Category

coding

## Prompt

Review this Bash script for bugs and safety issues:

```bash
#!/usr/bin/env bash

TARGET=$1

if [ -z $TARGET ]; then
  echo "missing target"
  exit 1
fi

rm -rf $TARGET/*
```

Explain what is dangerous and provide a safer version.
