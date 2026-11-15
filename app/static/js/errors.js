// Plain messages for each error code. Every code in docs/api.md has its own entry.

const TEXT = {
  rate_limited: { title: "Slow down a little", body: "Too many requests came from your connection in a short time. Wait a minute, then try again.", icon: "clock" },
  quota: { title: "Today's demo budget is used up", body: "The hosted demo has a daily limit of model calls and it has been reached. Screening opens again tomorrow. The reader and search keep working.", icon: "clock" },
  not_configured: { title: "Screening is switched off here", body: "This server has no Gemini API key set, so it cannot run the reasoning step. You can still browse and search the full text of the Act.", icon: "key" },
  llm_error: { title: "The model did not give a usable answer", body: "The reasoning step failed or returned something the screener could not check. Try again in a moment, or make the description shorter and more concrete.", icon: "alert" },
  network: { title: "No connection to the server", body: "The page could not reach the screener. Check your connection and try again.", icon: "wifiOff" },
  terms_required: { title: "Please accept the terms first", body: "The terms need to be accepted before anything is sent to the model.", icon: "info" },
  not_found: { title: "Not found", body: "That part of the Act could not be found.", icon: "info" },
  invalid_signature: { title: "This result can no longer be turned into a report", body: "This happens when the server restarted or the result changed since the screening. Screen the description again to download one.", icon: "refresh" },
  invalid_input: { title: "Check the description", body: "The description or the answers are not in the form the server accepts.", icon: "info" },
};

export function errorText(e) {
  const code = e && e.code ? e.code : "network";
  const msg = (e && e.message) || "";
  if (code === "invalid_input" && e.status === 413) {
    return { title: "That is too much text", body: "The request was larger than the server accepts. Shorten the description or the answers and try again.", icon: "info", code };
  }
  // "busy": too many screenings at once on the server. Older servers sent rate_limited with a "busy" message.
  if (code === "busy" || (code === "rate_limited" && /busy/i.test(msg))) {
    return { title: "The server is busy", body: "Several screenings are running at the same time. This is not a limit on you: try again in a few seconds.", icon: "clock", code: "busy" };
  }
  const ra = e && e.retryAfter;
  if (code === "rate_limited" && /\b(day|daily|today|tomorrow)\b/i.test(msg)) {
    const hours = ra ? Math.max(1, Math.round(ra / 3600)) : 0;
    return { title: "Today's limit for your connection is reached", body: `Your connection has used the screenings and questions it gets per day. The count starts again at midnight UTC${hours ? `, in about ${hours} hour${hours === 1 ? "" : "s"}` : ""}. The reader and search keep working.`, icon: "clock", code };
  }
  const wait = ra && ra <= 300 ? `Wait about ${ra} seconds, then try again.` : "Wait a minute, then try again.";
  if (code === "rate_limited" && /on this server|right now/i.test(msg)) {
    return { title: "Many people are screening right now", body: `The server takes a limited number of screenings per minute from everyone together. ${wait}`, icon: "clock", code };
  }
  if (code === "rate_limited") {
    return { ...TEXT.rate_limited, body: `Too many requests came from your connection in a short time. ${wait}`, code };
  }
  if (code === "invalid_input") {
    return { title: TEXT.invalid_input.title, body: msg || TEXT.invalid_input.body, icon: "info", code };
  }
  // The stream started but broke off: the server was reached.
  if (code === "network" && /broke/i.test(msg)) {
    return { title: "The connection broke off", body: "The connection broke before the answer was complete. Check your connection and try again.", icon: "wifiOff", code };
  }
  if (TEXT[code]) return { ...TEXT[code], code };
  // An unknown code from a newer server: say what happened without blaming the model.
  return { title: "Something went wrong", body: msg || "The server could not complete the request. Try again in a moment.", icon: "alert", code: "llm_error" };
}
