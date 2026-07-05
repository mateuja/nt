package main

import (
	"os"
	"testing"
)

func TestVersion(t *testing.T) {
	for _, arg := range []string{"--version", "-V"} {
		t.Run(arg, func(t *testing.T) {
			if os.Stdout == nil {
				t.Fatal("stdout unavailable")
			}
			if err := run([]string{arg}); err != nil {
				t.Fatalf("run(%q) returned error: %v", arg, err)
			}
		})
	}
}

func TestUnknownArgsUsageError(t *testing.T) {
	if err := run([]string{"bogus"}); err == nil {
		t.Fatal("expected usage error for unknown args, got nil")
	}
}
