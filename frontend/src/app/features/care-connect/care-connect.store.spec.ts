import { describe, expect, it } from 'vitest';
import { CareConnectStore } from './care-connect.store';
import { CareRequest, careAllowedActions, careLocalDate, careUtc } from './care-connect.model';

function requestInput(item: CareRequest) {
  return {
    facilityId: item.facilityId,
    serviceId: item.serviceId,
    profile: item.profile,
    contactName: item.contactName,
    phone: item.phone,
    needs: item.needs,
    note: item.note,
    preferredTime: item.preferredTime,
    proposedTime: '',
    confirmedTime: '',
  };
}

describe('Care connection interactive workflow', () => {
  it('starts with all seven request states and a hidden facility excluded from public discovery', () => {
    const store = new CareConnectStore();
    expect(new Set(store.requests().map((item) => item.status)).size).toBe(7);
    expect(store.facilities().filter((item) => item.published)).toHaveLength(5);
  });

  it('creates a pending request with consent and one history event', () => {
    const store = new CareConnectStore();
    const id = store.createRequest(requestInput(store.requests()[0]), 'submit-key');
    const created = store.requests().find((item) => item.id === id);
    expect(created?.status).toBe('SUBMITTED');
    expect(created?.version).toBe(1);
    expect(created?.history).toHaveLength(1);
    expect(created?.consentAt).toBeTruthy();
    expect(created?.confirmedTime).toBe('');
  });

  it('returns the same request when the same submission key is retried', () => {
    const store = new CareConnectStore();
    const input = requestInput(store.requests()[0]);
    const first = store.createRequest(input, 'retry');
    const second = store.createRequest(input, 'retry');
    expect(second).toBe(first);
    expect(store.requests()).toHaveLength(8);
  });

  it('blocks new requests when a facility is unpublished without removing history', () => {
    const store = new CareConnectStore();
    const facility = { ...store.facilities()[0], published: false };
    store.saveFacility(facility);
    expect(store.createRequest(requestInput(store.requests()[0]), 'new')).toBe('');
    expect(store.requests()).toHaveLength(7);
  });

  it('blocks new requests for a paused service', () => {
    const store = new CareConnectStore();
    const facility = structuredClone(store.facilities()[0]);
    facility.services[0].accepting = false;
    store.saveFacility(facility);
    expect(store.createRequest(requestInput(store.requests()[0]), 'new')).toBe('');
  });

  it('keeps preferred, proposed and confirmed times separate when a family accepts', () => {
    const store = new CareConnectStore();
    const request = store.requests()[0];
    expect(store.act(request.id, request.version, 'ACCEPT_SCHEDULE', false)).toBe('');
    const updated = store.requests()[0];
    expect(updated.status).toBe('CONFIRMED');
    expect(updated.confirmedTime).toBe(request.proposedTime);
    expect(updated.preferredTime).toBe(request.preferredTime);
    expect(updated.version).toBe(request.version + 1);
    expect(updated.history.at(-1)?.actor).toBe('family');
  });

  it('rejects accepting a stale schedule proposal', () => {
    const store = new CareConnectStore();
    const request = store.requests()[0];
    expect(
      store.act(
        request.id,
        request.version,
        'PROPOSE_SCHEDULE',
        true,
        'New time',
        careLocalDate(6, 10),
      ),
    ).toBe('');
    expect(store.act(request.id, request.version, 'ACCEPT_SCHEDULE', false)).toBe('CONFLICT');
    expect(store.requests()[0].status).toBe('SCHEDULE_PROPOSED');
  });

  it('requires a reason before declining or cancelling', () => {
    const store = new CareConnectStore();
    const request = store.requests().find((item) => item.status === 'IN_REVIEW') as CareRequest;
    expect(store.act(request.id, request.version, 'DECLINE', true, '  ')).toBe('REASON');
    expect(store.act(request.id, request.version, 'CANCEL', false)).toBe('REASON');
  });

  it('rejects a proposal in the past', () => {
    const store = new CareConnectStore();
    const request = store.requests()[0];
    expect(
      store.act(
        request.id,
        request.version,
        'PROPOSE_SCHEDULE',
        true,
        'Please check',
        careLocalDate(-1),
      ),
    ).toBe('FUTURE');
  });

  it('does not let facility staff accept a family proposal or act on another facility', () => {
    const store = new CareConnectStore();
    const request = store.requests()[0];
    expect(store.act(request.id, request.version, 'ACCEPT_SCHEDULE', true)).toBe('ACTION');
    expect(careAllowedActions({ ...request, facilityId: 'binh-an' }, true)).toEqual([]);
  });

  it('blocks completing a consultation before its confirmed time', () => {
    const store = new CareConnectStore();
    const request = store.requests().find((item) => item.status === 'CONFIRMED') as CareRequest;
    expect(store.act(request.id, request.version, 'COMPLETE', true)).toBe('ACTION');
  });

  it('keeps closed requests immutable and records a cancellation reason', () => {
    const store = new CareConnectStore();
    const request = store.requests()[0];
    expect(store.act(request.id, request.version, 'CANCEL', false, 'Family plans changed')).toBe(
      '',
    );
    const cancelled = store.requests()[0];
    expect(cancelled.history.at(-1)?.message).toBe('Family plans changed');
    expect(careAllowedActions(cancelled, true)).toEqual([]);
    expect(careAllowedActions(cancelled, false)).toEqual([]);
    expect(store.act(cancelled.id, cancelled.version, 'START_REVIEW', true)).toBe('ACTION');
  });

  it('converts Vietnam wall time and rejects malformed or impossible calendar dates safely', () => {
    expect(careUtc('2028-02-29T09:15')).toBe('2028-02-29T02:15:00.000Z');
    for (const value of [
      '',
      'invalid',
      '2027-02-29T09:15',
      '2026-02-30T09:15',
      '2026-13-01T09:15',
      '2026-10-23T24:00',
      '2026-10-23T09:15:00',
      '2026-1-01T09:15',
    ]) {
      expect(careUtc(value), value).toBe('');
    }
  });

  it('rejects malformed schedule proposals without throwing or changing history', () => {
    const store = new CareConnectStore();
    const request = store.requests()[0];
    for (const value of ['invalid', '2027-02-29T09:15', '', '2026-10-23T24:00']) {
      expect(
        store.act(request.id, request.version, 'PROPOSE_SCHEDULE', true, 'Another time', value),
      ).toBe('FUTURE');
    }
    expect(store.requests()[0]).toEqual(request);
  });

  it('rejects a missing or invalid preferred time before staff confirmation', () => {
    const store = new CareConnectStore();
    const request = store.requests().find((item) => item.status === 'IN_REVIEW') as CareRequest;
    for (const value of ['', 'invalid']) {
      store.requests.update((items) =>
        items.map((item) => (item.id === request.id ? { ...item, preferredTime: value } : item)),
      );
      expect(store.act(request.id, request.version, 'CONFIRM_PREFERRED', true)).toBe('FUTURE');
      expect(store.requests().find((item) => item.id === request.id)?.status).toBe('IN_REVIEW');
    }
  });

  it('rejects a missing or invalid proposed time before family acceptance', () => {
    const store = new CareConnectStore();
    const request = store.requests()[0];
    for (const value of ['', 'invalid']) {
      store.requests.update((items) =>
        items.map((item) => (item.id === request.id ? { ...item, proposedTime: value } : item)),
      );
      expect(store.act(request.id, request.version, 'ACCEPT_SCHEDULE', false)).toBe('FUTURE');
      expect(store.requests()[0].status).toBe('SCHEDULE_PROPOSED');
    }
  });

  it('keeps each proposal time in history when staff revise a schedule', () => {
    const store = new CareConnectStore();
    const original = store.requests()[0];
    const nextTime = careLocalDate(7, 15);
    const oldProposal = original.history.at(-1);
    expect(oldProposal?.scheduledTime).toBe(original.proposedTime);
    expect(
      store.act(
        original.id,
        original.version,
        'PROPOSE_SCHEDULE',
        true,
        'Updated availability',
        nextTime,
      ),
    ).toBe('');
    const revised = store.requests()[0];
    expect(revised.history.at(-2)?.scheduledTime).toBe(original.proposedTime);
    expect(revised.history.at(-1)?.scheduledTime).toBe(careUtc(nextTime));
    expect(oldProposal?.scheduledTime).toBe(original.proposedTime);
    expect(store.act(revised.id, revised.version, 'ACCEPT_SCHEDULE', false)).toBe('');
    const confirmed = store.requests()[0];
    expect(confirmed.history.at(-1)?.scheduledTime).toBe(careUtc(nextTime));
    expect(confirmed.history.at(-1)?.actor).toBe('family');
  });

  it('uses coherent seed histories with ordered times and matching request versions', () => {
    const store = new CareConnectStore();
    for (const request of store.requests()) {
      expect(request.version).toBe(request.history.length);
      expect(request.history.at(-1)?.status).toBe(request.status);
      expect(request.updatedAt).toBe(request.history.at(-1)?.at);
      for (let index = 1; index < request.history.length; index++) {
        expect(Date.parse(request.history[index].at)).toBeGreaterThan(
          Date.parse(request.history[index - 1].at),
        );
      }
      if (request.status === 'COMPLETED') {
        expect(Date.parse(request.updatedAt)).toBeGreaterThan(Date.parse(request.confirmedTime));
      }
      if (request.status === 'CONFIRMED') {
        expect(request.history.at(-2)?.status).toBe('SCHEDULE_PROPOSED');
        expect(request.history.at(-1)?.actor).toBe('family');
      }
    }
  });

  it('blocks stale or invalid preferred times when creating a request', () => {
    const store = new CareConnectStore();
    const input = requestInput(store.requests()[0]);
    for (const value of ['', 'invalid', careUtc(careLocalDate(-1))]) {
      expect(store.createRequest({ ...input, preferredTime: value }, `invalid-${value}`)).toBe('');
    }
    expect(store.requests()).toHaveLength(7);
  });

  it('computes explainable rule-based recommendations and treats price=0 as unpublished missing info', () => {
    const store = new CareConnectStore();
    // Publish thanh-tam (which has price=0) to verify price=0 is never treated as free
    const thanhTam = store.facilities().find((f) => f.id === 'thanh-tam');
    if (thanhTam) {
      store.saveFacility({ ...thanhTam, published: true });
    }
    const recs = store.recommend({
      region: 'hcm',
      serviceId: 'longstay',
      supportLevel: 'L2',
      budgetMaxVnd: 15000000,
      priorityTags: ['nursing', 'garden'],
    });
    expect(recs[0].facilityId).toBe('an-nhien');
    expect(recs[0].score).toBe(100);
    expect(recs[0].rulesVersion).toBe('care-rec-v1');
    const thanhTamRec = recs.find((r) => r.facilityId === 'thanh-tam');
    expect(thanhTamRec?.missing).toContain('BUDGET_NOT_PUBLISHED');
    expect(thanhTamRec?.reasons.some((r) => r.code === 'WITHIN_BUDGET')).toBe(false);
  });

  it('caps facility comparison at 3 facilities and checks unit compatibility', () => {
    const store = new CareConnectStore();
    expect(store.toggleCompare('an-nhien')).toBe(true);
    expect(store.toggleCompare('binh-an')).toBe(true);
    expect(store.toggleCompare('vuon-nang')).toBe(true);
    expect(store.toggleCompare('song-khoe')).toBe(false);
    expect(store.comparedFacilities()).toHaveLength(3);
    expect(store.canCompareServicePrice(store.comparedFacilities(), 'longstay')).toBe(true);
  });

  it('enforces consultation slot capacity and releases capacity on cancellation', () => {
    const store = new CareConnectStore();
    // slot-an-nhien-2 is already at capacity (2/2)
    const input = requestInput(store.requests()[0]);
    expect(store.createRequest({ ...input, slotId: 'slot-an-nhien-2' }, 'slot-full')).toBe('');

    // slot-an-nhien-1 has 1/3 booked -> booking increments to 2/3
    const createdId = store.createRequest({ ...input, slotId: 'slot-an-nhien-1' }, 'slot-avail');
    expect(createdId).toBeTruthy();
    expect(store.slots().find((s) => s.id === 'slot-an-nhien-1')?.bookedCount).toBe(2);

    // Cancelling releases the slot back to 1/3
    expect(store.act(createdId, 1, 'CANCEL', false, 'Change of plans')).toBe('');
    expect(store.slots().find((s) => s.id === 'slot-an-nhien-1')?.bookedCount).toBe(1);
  });

  it('accepts feedback only for COMPLETED requests and updates ratings only after moderation approval', () => {
    const store = new CareConnectStore();
    const submitted = store.requests().find((r) => r.status === 'SUBMITTED') as CareRequest;
    const completed = store.requests().find((r) => r.status === 'COMPLETED') as CareRequest;

    expect(store.submitFeedback(submitted.id, 5, ['DEDICATED'], 'Not completed yet')).toBe(false);
    const fb = store.submitFeedback(completed.id, 5, ['DEDICATED', 'CLEAN'], 'Very helpful');
    expect(fb).not.toBe(false);
    if (fb !== false) {
      expect(fb.moderationStatus).toBe('pending');
      // Duplicate feedback on same request is rejected
      expect(store.submitFeedback(completed.id, 4, [], 'Duplicate')).toBe(false);
      // Approve feedback -> included in public feedback list
      expect(store.moderateFeedback(fb.id, 'approved')).toBe(true);
      expect(store.feedbackForFacility(completed.facilityId).some((item) => item.id === fb.id)).toBe(
        true,
      );
    }
  });
});
