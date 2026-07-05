// Package main is the entry point for the Go rewrite of nt.
//
// It is intentionally a minimal stub for now: it satisfies the
// `nt --version` / `nt -V` contract (see docs/cli-contract.md) and
// returns a usage error for anything else, mirroring the Python v1
// stub in py/src/nt/__main__.py. Real command handling lands as the
// Go port progresses against the docs/ contracts.
package main

import (
	"fmt"
	"os"
)

const version = "0.1.0"

func main() {
	if err := run(os.Args[1:]); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
}

func run(args []string) error {
	switch {
	case len(args) == 1 && (args[0] == "--version" || args[0] == "-V"):
		fmt.Printf("nt %s\n", version)
		return nil
	default:
		return fmt.Errorf("not implemented yet")
	}
}
