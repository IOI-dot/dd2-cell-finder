# docker/ (planned)

Images for the flow, agent, backend and web, and a compose file. `given/`, `pdk/`, `tests/` and
`src/dd2/` are mounted read-only, which is the prevention layer for overview 4.3 rule 4. The agent
policy's digest check only detects changes. The course `dd2-layout-tools` image is built from the
student pack's `container/` unchanged. Tasks T065–T066.
