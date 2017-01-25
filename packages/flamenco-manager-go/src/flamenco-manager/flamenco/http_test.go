package flamenco

import (
	"time"

	"github.com/stretchr/testify/assert"

	check "gopkg.in/check.v1"
)

type HttpTestSuite struct{}

var _ = check.Suite(&HttpTestSuite{})

func (s *HttpTestSuite) TestParseDates(c *check.C) {
	parsed_iso, err1 := time.Parse(IsoFormat, "2017-01-23T13:04:05+0200")
	parsed_ms, err2 := time.Parse(LastModifiedHeaderFormat, "2017-01-23 13:04:05+02:00")
	assert.Nil(c, err1)
	assert.Nil(c, err2)
	assert.Equal(c, parsed_iso, parsed_ms)
}
