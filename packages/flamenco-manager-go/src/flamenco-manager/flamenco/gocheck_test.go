package flamenco

import (
	"testing"

	check "gopkg.in/check.v1"
)

// Hook up gocheck into the "go test" runner.
// You only need one of these per package, or tests will run multiple times.
func TestWithGocheck(t *testing.T) { check.TestingT(t) }
