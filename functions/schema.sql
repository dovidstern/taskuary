-- One row per thing a visitor did in the demo. Deliberately small: no ip, no user agent string,
-- no cookie - Sid is a random id that lives in sessionStorage and dies with the tab.
CREATE TABLE IF NOT EXISTS ev (
  Id      INTEGER PRIMARY KEY,
  At      TEXT NOT NULL,      -- ISO8601, server clock
  Sid     TEXT NOT NULL,      -- per-tab, not per-person
  Kind    TEXT NOT NULL,      -- open | tab | row | verdict | ask | watch | dwell | leave | cta
  What    TEXT DEFAULT '',    -- which tab, which verdict, which button
  N       INTEGER DEFAULT 0,  -- seconds, for dwell/leave
  Page    TEXT DEFAULT '',
  Ref     TEXT DEFAULT '',    -- referrer host only
  Country TEXT DEFAULT '',
  Mobile  INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ev_at ON ev(At);
CREATE INDEX IF NOT EXISTS ev_sid ON ev(Sid);
