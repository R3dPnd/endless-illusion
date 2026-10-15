import { Router } from "express";
import { addProgram, confirmProposal, dismissLead, HttpError, listBounties, rejectProposal, trackLead } from "../db/bounties.mjs";

/** Wrap a handler so HttpErrors become their status and anything else a 500. */
export const handle = (fn) => (req, res) => {
  try {
    res.json(fn(req) ?? { ok: true });
  } catch (err) {
    const status = err instanceof HttpError ? err.status : 500;
    if (status === 500) console.error("[api]", err);
    res.status(status).json({ error: err.message });
  }
};

const proposalId = (req) => {
  const id = Number(req.params.id);
  if (!Number.isInteger(id)) throw new HttpError(400, "bad proposal id");
  return id;
};

const leadUrl = (req) => {
  const url = req.body?.normalizedUrl;
  if (typeof url !== "string" || !url) throw new HttpError(400, "normalizedUrl is required");
  return url;
};

export function bountyRoutes(db) {
  const r = Router();
  r.get("/bounties", handle(() => listBounties(db)));
  r.post("/programs", handle((req) => ({ programId: addProgram(db, req.body ?? {}) })));
  r.post("/leads/track", handle((req) => ({ programId: trackLead(db, leadUrl(req)) })));
  r.post("/leads/dismiss", handle((req) => dismissLead(db, leadUrl(req))));
  r.post("/proposals/:id/confirm", handle((req) => ({ snapshotId: confirmProposal(db, proposalId(req)) })));
  r.post("/proposals/:id/reject", handle((req) => rejectProposal(db, proposalId(req))));
  return r;
}
