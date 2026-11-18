// 5.3.3 vendor probe — does resolveTimelineStart keep <StartFrame> and <StartTC> honest?
// Cases mirror the release claims: (1) label agrees with frame in the caller's counting mode,
// (2) drop-frame arithmetic only at 29.97/59.94 (SMPTE 12M), (3) invalid labels raise instead
// of silently becoming frame 0. Independent expectations, not the module's own math.
const B = require(process.env.DRP_MOD);

const ok = [];
const fail = [];
function check(name, cond, detail) {
  (cond ? ok : fail).push(name + (detail ? `  [${detail}]` : ""));
}

// Independent SMPTE 12M drop-frame label for 29.97 (frames counted from 00:00:00;00)
function dfLabel(frames) {
  const D = 2, perMin = 1798, per10 = 17982;
  const tens = Math.floor(frames / per10), rem = frames % per10;
  let n = frames + D * 9 * tens;
  if (rem > D) n += D * Math.floor((rem - D) / perMin);
  const s = Math.floor(n / 30);
  const p = (v) => String(v).padStart(2, "0");
  return `${p(Math.floor(s / 3600))}:${p(Math.floor(s / 60) % 60)}:${p(s % 60)};${p(n % 30)}`;
}

// 1. explicit startFrame + DF label at 29.97: label must round-trip to the same frame
let r = B.resolveTimelineStart({ startFrame: 108000, startTimecode: "01:00:00;00" }, 29.97);
check("29.97 DF: StartFrame kept", r.startFrame === 108000, JSON.stringify(r));
check("29.97 DF: label uses ';' (drop-frame mode signalled by caller)", r.startTimecode.includes(";"), r.startTimecode);
check("29.97 DF: label round-trips to the SAME frame",
      B.timecodeToFrames(r.startTimecode, 29.97) === 108000, r.startTimecode);
check("29.97 DF: label matches independent SMPTE 12M math",
      r.startTimecode === dfLabel(108000), `module=${r.startTimecode} independent=${dfLabel(108000)}`);

// 2. label-only start at 29.97: frame must be the DF count of the label (01:00:00;00 = 107892)
r = B.resolveTimelineStart({ startTimecode: "01:00:00;00" }, 29.97);
check("label-only 01:00:00;00 @29.97 -> frame 107892", r.startFrame === 107892, JSON.stringify(r));

// 3. NDF at 24 fps: ';' is NOT drop-frame arithmetic territory (29.97/59.94 only). Record behavior.
let threw24 = null;
try { r = B.resolveTimelineStart({ startFrame: 108000, startTimecode: "01:00:00;00" }, 24); }
catch (e) { threw24 = e; }
if (threw24) check("';' label at 24 fps raises", true, threw24.constructor.name + ": " + threw24.message.slice(0, 120));
else check("';' label at 24 fps: StartFrame kept and labelled NDF",
           r.startFrame === 108000 && !r.startTimecode.includes(";"), JSON.stringify(r));

// 4. invalid label RAISES (was: silently frame 0 before 5.3.3)
for (const bad of ["not-a-timecode", "01:00:00:xx", "99:99:99:99"]) {
  let e = null, val = null;
  try { val = B.timecodeToFrames(bad, 29.97); } catch (err) { e = err; }
  check(`invalid label '${bad}' raises (no silent frame 0)`, e !== null && val !== 0,
        e ? e.constructor.name + ": " + e.message.slice(0, 90) : `returned ${val}`);
}

// 5. out-of-range counted as invalid, not valid (release: fields out of range no longer counted valid)
let e = null;
try { B.timecodeToFrames("00:01:00;00", 29.97); } catch (err) { e = err; }  // SMPTE 12M skips ;00/;01 at non-tenth minutes
check("skipped DF number 00:01:00;00 raises", e !== null, e ? e.message.slice(0, 90) : "accepted");

// 6. NDF round-trip sanity at 25 fps: 01:00:00:00 -> 90000
r = B.resolveTimelineStart({ startTimecode: "01:00:00:00" }, 25);
check("25 fps NDF 01:00:00:00 -> 90000", r.startFrame === 90000, JSON.stringify(r));

console.log("PASS", ok.length);
ok.forEach((s) => console.log("  +", s));
if (fail.length) { console.log("FAIL", fail.length); fail.forEach((s) => console.log("  -", s)); }
process.exit(fail.length ? 2 : 0);
