import { writeFileSync } from "node:fs";
import { library } from "../src/library";

/* The model is told the language and the components from the library itself, so the two cannot drift. */
const text = library.prompt({
  preamble: "Below are the language and the only components you may use.",
  examples: [`root = Report([v, why, l, next])
v = Verdict("run:A-0000-01")
why = Note("The first ordering needed met1, and a later one did not.")
l = Layout3D("cell:A-0000-01/a_x_r1")
next = Choices([a, b])
a = Choice("Compare sizings", "Compare hd and stack sizing for this cell", "Speed against width")
b = Choice("See it switch", "Show the transient simulation of this cell", "The waveform the check judged")`],
});
writeFileSync("../prompts/ui_library.md", `${text}\n`);
console.log(`wrote prompts/ui_library.md (${text.length} characters)`);
