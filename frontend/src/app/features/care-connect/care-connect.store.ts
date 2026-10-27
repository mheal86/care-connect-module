import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
import { CARE_CONNECT_API, CareConnectApi } from '../../core/api/care-connect.service';
import {
  CareAction,
  CareConsultSlot,
  CareFacility,
  CareFeedbackItem,
  CareHistory,
  CareRecommendation,
  CareRecommendationCriteria,
  CareRequest,
  CareServiceId,
  CareStatus,
  careAllowedActions,
  careLocalDate,
  careUtc,
  computeCareRecommendations,
} from './care-connect.model';

const FACILITIES: CareFacility[] = [
  {
    id: 'an-nhien',
    key: 'AN_NHIEN',
    region: 'hcm',
    type: 'residential',
    addressKey: 'AN_NHIEN',
    descriptionKey: 'RESIDENTIAL',
    published: true,
    updatedAt: '2026-10-20',
    amenities: ['nursing', 'garden', 'accessible'],
    lat: 10.7769,
    lng: 106.7009,
    geoVerified: true,
    verifiedBadge: true,
    suitableFor: ['L1', 'L2', 'L3'],
    supportTags: ['nursing', 'rehab', 'garden', 'accessible'],
    distanceKm: 3.4,
    averageRating: 4.8,
    feedbackCount: 2,
    services: [
      { id: 'longstay', price: 12000000, unit: 'month', accepting: true },
      { id: 'daycare', price: 450000, unit: 'day', accepting: true },
      { id: 'rehab', price: 350000, unit: 'session', accepting: true },
    ],
  },
  {
    id: 'binh-an',
    key: 'BINH_AN',
    region: 'hcm',
    type: 'health',
    addressKey: 'BINH_AN',
    descriptionKey: 'HEALTH',
    published: true,
    updatedAt: '2026-10-19',
    amenities: ['therapy', 'accessible', 'family'],
    lat: 10.7924,
    lng: 106.6881,
    geoVerified: true,
    verifiedBadge: true,
    suitableFor: ['L1', 'L2'],
    supportTags: ['rehab', 'accessible', 'family'],
    distanceKm: 5.1,
    averageRating: 4.6,
    feedbackCount: 1,
    services: [
      { id: 'rehab', price: 400000, unit: 'session', accepting: true },
      { id: 'daycare', price: 500000, unit: 'day', accepting: true },
    ],
  },
  {
    id: 'vuon-nang',
    key: 'VUON_NANG',
    region: 'hanoi',
    type: 'residential',
    addressKey: 'VUON_NANG',
    descriptionKey: 'RESIDENTIAL',
    published: true,
    updatedAt: '2026-10-18',
    amenities: ['garden', 'nursing', 'family'],
    lat: 21.0285,
    lng: 105.8542,
    geoVerified: true,
    verifiedBadge: true,
    suitableFor: ['L2', 'L3'],
    supportTags: ['nursing', 'garden', 'family'],
    distanceKm: 4.2,
    averageRating: 4.7,
    feedbackCount: 1,
    services: [
      { id: 'longstay', price: 15000000, unit: 'month', accepting: true },
      { id: 'daycare', price: 550000, unit: 'day', accepting: false },
    ],
  },
  {
    id: 'song-khoe',
    key: 'SONG_KHOE',
    region: 'danang',
    type: 'health',
    addressKey: 'SONG_KHOE',
    descriptionKey: 'HEALTH',
    published: true,
    updatedAt: '2026-10-17',
    amenities: ['therapy', 'nursing', 'accessible'],
    lat: 16.0544,
    lng: 108.2022,
    geoVerified: true,
    verifiedBadge: false,
    suitableFor: ['L1', 'L2'],
    supportTags: ['rehab', 'nursing', 'accessible'],
    distanceKm: 2.8,
    averageRating: 0,
    feedbackCount: 0,
    services: [{ id: 'rehab', price: 300000, unit: 'session', accepting: true }],
  },
  {
    id: 'mai-am',
    key: 'MAI_AM',
    region: 'hcm',
    type: 'daycare',
    addressKey: 'MAI_AM',
    descriptionKey: 'DAYCARE',
    published: true,
    updatedAt: '2026-10-16',
    amenities: ['family', 'garden', 'accessible'],
    lat: 10.7626,
    lng: 106.6602,
    geoVerified: true,
    verifiedBadge: true,
    suitableFor: ['L1'],
    supportTags: ['family', 'garden', 'accessible'],
    distanceKm: 2.1,
    averageRating: 4.9,
    feedbackCount: 1,
    services: [{ id: 'daycare', price: 380000, unit: 'day', accepting: true }],
  },
  {
    id: 'thanh-tam',
    key: 'THANH_TAM',
    region: 'hanoi',
    type: 'residential',
    addressKey: 'THANH_TAM',
    descriptionKey: 'RESIDENTIAL',
    published: false,
    updatedAt: '2026-10-15',
    amenities: ['nursing', 'family'],
    geoVerified: false,
    verifiedBadge: false,
    suitableFor: ['L2', 'L3'],
    supportTags: ['nursing', 'family'],
    services: [{ id: 'longstay', price: 0, unit: 'month', accepting: true }],
  },
];

function createSeedSlots(): CareConsultSlot[] {
  const slots: CareConsultSlot[] = [];
  for (const facilityId of ['an-nhien', 'binh-an', 'vuon-nang', 'song-khoe', 'mai-am']) {
    const start1 = careUtc(careLocalDate(2, 9));
    const end1 = careUtc(careLocalDate(2, 10));
    const start2 = careUtc(careLocalDate(3, 14));
    const end2 = careUtc(careLocalDate(3, 15));
    const start3 = careUtc(careLocalDate(4, 9));
    const end3 = careUtc(careLocalDate(4, 10));
    slots.push(
      {
        id: `slot-${facilityId}-1`,
        facilityId,
        startsAt: start1,
        endsAt: end1,
        capacity: 3,
        bookedCount: 1,
        active: true,
      },
      {
        id: `slot-${facilityId}-2`,
        facilityId,
        startsAt: start2,
        endsAt: end2,
        capacity: 2,
        bookedCount: 2,
        active: true,
      },
      {
        id: `slot-${facilityId}-3`,
        facilityId,
        startsAt: start3,
        endsAt: end3,
        capacity: 4,
        bookedCount: 0,
        active: true,
      },
    );
  }
  return slots;
}

function createSeedFeedbacks(): CareFeedbackItem[] {
  const createdAt = careUtc(careLocalDate(-2, 15));
  return [
    {
      id: 'fb-seed-1',
      requestId: 'TV-SEED-0001',
      facilityId: 'an-nhien',
      rating: 5,
      tags: ['DEDICATED', 'CLEAR_INFO'],
      comment: 'Nhân viên tư vấn rõ ràng về lịch sinh hoạt và chế độ dinh dưỡng.',
      moderationStatus: 'approved',
      createdAt,
    },
    {
      id: 'fb-seed-2',
      requestId: 'TV-SEED-0002',
      facilityId: 'an-nhien',
      rating: 4,
      tags: ['CLEAN', 'ON_TIME'],
      comment: 'Khuôn viên thoáng mát, giải đáp kỹ các câu hỏi của gia đình.',
      moderationStatus: 'pending',
      createdAt,
    },
  ];
}

function createSeedRequest(
  index: number,
  status: CareStatus,
  facilityId = 'an-nhien',
): CareRequest {
  const at = careUtc(careLocalDate(-index - 1, 10));
  const preferredTime = careUtc(careLocalDate(status === 'COMPLETED' ? -1 : 3, 9));
  const proposedTime = ['SCHEDULE_PROPOSED', 'CONFIRMED'].includes(status)
    ? careUtc(careLocalDate(4, 14))
    : '';
  const confirmedTime =
    status === 'CONFIRMED' ? proposedTime : status === 'COMPLETED' ? preferredTime : '';
  const afterCreation = (hours: number) =>
    new Date(Date.parse(at) + hours * 60 * 60 * 1000).toISOString();
  const history: CareHistory[] = [
    { status: 'SUBMITTED', at, message: '', actor: 'family', scheduledTime: preferredTime },
  ];
  if (status === 'CANCELLED') {
    history.push({
      status,
      at: afterCreation(1),
      message: 'CARE.SAMPLE.CANCELLATION',
      actor: 'family',
    });
  } else if (status !== 'SUBMITTED') {
    history.push({ status: 'IN_REVIEW', at: afterCreation(1), message: '', actor: 'staff' });
    if (proposedTime) {
      history.push({
        status: 'SCHEDULE_PROPOSED',
        at: afterCreation(2),
        message: 'CARE.SAMPLE.PROPOSAL',
        actor: 'staff',
        scheduledTime: proposedTime,
      });
    }
    if (confirmedTime) {
      history.push({
        status: 'CONFIRMED',
        at: afterCreation(proposedTime ? 3 : 2),
        message: '',
        actor: proposedTime ? 'family' : 'staff',
        scheduledTime: confirmedTime,
      });
    }
    if (status === 'COMPLETED') {
      history.push({
        status,
        at: new Date(Date.parse(confirmedTime) + 60 * 60 * 1000).toISOString(),
        message: '',
        actor: 'staff',
        scheduledTime: confirmedTime,
      });
    }
    if (status === 'DECLINED') {
      history.push({
        status,
        at: afterCreation(2),
        message: 'CARE.SAMPLE.DECLINED',
        actor: 'staff',
      });
    }
  }
  const request: CareRequest = {
    id: `TV-${new Date().getFullYear()}-${String(128 + index).padStart(4, '0')}`,
    facilityId,
    serviceId: index % 2 === 0 ? 'longstay' : 'rehab',
    profile: 'an',
    contactName: 'Người liên hệ mẫu',
    phone: '0900000000',
    needs: 'CARE.SAMPLE.NEEDS',
    note: '',
    preferredTime,
    proposedTime,
    confirmedTime,
    status,
    version: history.length,
    updatedAt: history[history.length - 1].at,
    consentAt: at,
    history,
  };
  return request;
}

/** Interactive store supporting both fixture mode (/care-connect-v2, unit specs) and HTTP adapter (/care-connect). */
function resolveCareConnectApi(): CareConnectApi | false {
  try {
    return inject(CARE_CONNECT_API, { optional: true }) || false;
  } catch {
    return false;
  }
}

@Injectable()
export class CareConnectStore {
  api: CareConnectApi | false = resolveCareConnectApi();
  fixture = !this.api || this.api.mode === 'fixture';
  loading = signal(false);
  busy = signal(false);
  error = signal('');
  memberIds = signal<string[]>([]);
  managerIds = signal<string[]>([]);
  profiles = signal<{ id: string; name: string }[]>([]);
  facilities = signal<CareFacility[]>(structuredClone(FACILITIES));
  requests = signal<CareRequest[]>([
    createSeedRequest(0, 'SCHEDULE_PROPOSED'),
    createSeedRequest(1, 'SUBMITTED'),
    createSeedRequest(2, 'CONFIRMED'),
    createSeedRequest(3, 'IN_REVIEW'),
    createSeedRequest(4, 'COMPLETED'),
    createSeedRequest(5, 'DECLINED'),
    createSeedRequest(6, 'CANCELLED'),
  ]);
  slots = signal<CareConsultSlot[]>(createSeedSlots());
  feedbacks = signal<CareFeedbackItem[]>(createSeedFeedbacks());
  compareIds = signal<string[]>([]);
  recommendations = signal<CareRecommendation[]>([]);
  comparedFacilities = computed<CareFacility[]>(() => {
    const ids = this.compareIds();
    const list = this.facilities();
    return ids
      .map((id) => list.find((item) => item.id === id))
      .filter((item): item is CareFacility => Boolean(item));
  });
  // The same key returns the same result when the submission is retried.
  submittedKeys = new Map<string, string>();

  constructor() {
    if (!this.fixture) {
      this.facilities.set([]);
      this.requests.set([]);
      this.slots.set([]);
      this.feedbacks.set([]);
    }
  }

  async load(scope: 'mine' | 'inbox' = 'mine') {
    const api = this.api;
    if (!api || this.fixture) return;
    this.loading.set(true);
    this.error.set('');
    try {
      const me = await firstValueFrom(api.getMe());
      if (me !== false) {
        this.memberIds.set(me.facilityIds);
        this.managerIds.set(me.managerIds);
        this.profiles.set(me.profiles);
      }
      this.facilities.set(await firstValueFrom(api.fetchFacilities()));
      this.requests.set(await firstValueFrom(api.fetchRequests(scope)));
      const facilities = this.facilities();
      const [slots, feedback] = await Promise.all([
        Promise.all(facilities.map((f) => firstValueFrom(api.listSlots(f.id)))),
        Promise.all(facilities.map((f) => firstValueFrom(api.listFeedback(f.id)))),
      ]);
      this.slots.set(slots.flat());
      this.feedbacks.set(feedback.flat());
    } catch (error) {
      this.setError(error instanceof HttpErrorResponse ? error : false);
    } finally {
      this.loading.set(false);
    }
  }

  setError(error: HttpErrorResponse | false) {
    this.error.set(
      error && error.status === 409
        ? 'CONFLICT'
        : error && error.status === 403
          ? 'FORBIDDEN'
          : 'API_ERROR',
    );
    return this.error();
  }

  async submitRequest(input: Parameters<CareConnectStore['createRequest']>[0], key: string) {
    const api = this.api;
    if (!api || this.fixture) return this.createRequest(input, key);
    this.busy.set(true);
    this.error.set('');
    try {
      const request = await firstValueFrom(api.createRequest(input, key));
      if (request === false) return '';
      this.requests.update((items) => [request, ...items.filter((r) => r.id !== request.id)]);
      return request.id;
    } catch (error) {
      this.setError(error instanceof HttpErrorResponse ? error : false);
      return '';
    } finally {
      this.busy.set(false);
    }
  }

  async applyRequestAction(
    id: string,
    version: number,
    action: CareAction,
    staff: boolean,
    message = '',
    time = '',
  ) {
    const api = this.api;
    if (!api || this.fixture) return this.act(id, version, action, staff, message, time);
    this.busy.set(true);
    this.error.set('');
    try {
      const request = await firstValueFrom(
        api.actOnRequest(
          id,
          version,
          action,
          message,
          action === 'PROPOSE_SCHEDULE' ? careUtc(time) : '',
          staff,
        ),
      );
      if (request === false) return 'API_ERROR';
      this.requests.update((items) => items.map((r) => (r.id === id ? request : r)));
      this.slots.set(
        (
          await Promise.all(this.facilities().map((f) => firstValueFrom(api.listSlots(f.id))))
        ).flat(),
      );
      return '';
    } catch (error) {
      const code = this.setError(error instanceof HttpErrorResponse ? error : false);
      if (code === 'CONFLICT') {
        this.requests.set(await firstValueFrom(api.fetchRequests(staff ? 'inbox' : 'mine')));
      }
      return code;
    } finally {
      this.busy.set(false);
    }
  }

  async persistFacility(facility: CareFacility) {
    const api = this.api;
    if (!api || this.fixture) {
      this.saveFacility(facility);
      return true;
    }
    this.busy.set(true);
    this.error.set('');
    try {
      const saved = await firstValueFrom(api.saveFacility(facility));
      if (saved === false) return false;
      this.facilities.update((items) => [...items.filter((f) => f.id !== saved.id), saved]);
      return true;
    } catch (error) {
      this.setError(error instanceof HttpErrorResponse ? error : false);
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  async sendFeedback(id: string, rating: number, tags: string[], comment: string) {
    const api = this.api;
    if (!api || this.fixture) return this.submitFeedback(id, rating, tags, comment) !== false;
    this.busy.set(true);
    this.error.set('');
    try {
      const saved = await firstValueFrom(api.submitFeedback(id, rating, tags, comment));
      if (saved === false) return false;
      this.feedbacks.update((items) => [saved, ...items.filter((f) => f.id !== saved.id)]);
      return true;
    } catch (error) {
      this.setError(error instanceof HttpErrorResponse ? error : false);
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  async reviewFeedback(id: string, status: 'approved' | 'rejected') {
    const api = this.api;
    if (!api || this.fixture) return this.moderateFeedback(id, status);
    this.busy.set(true);
    this.error.set('');
    try {
      const saved = await firstValueFrom(api.moderateFeedback(id, status));
      if (saved === false) return false;
      this.feedbacks.update((items) => items.map((f) => (f.id === id ? saved : f)));
      this.facilities.set(await firstValueFrom(api.fetchFacilities()));
      return true;
    } catch (error) {
      this.setError(error instanceof HttpErrorResponse ? error : false);
      return false;
    } finally {
      this.busy.set(false);
    }
  }

  createRequest(
    input: Omit<CareRequest, 'id' | 'status' | 'version' | 'updatedAt' | 'history' | 'consentAt'>,
    key: string,
  ) {
    const previousId = this.submittedKeys.get(key);
    if (previousId) return previousId;
    const facility = this.facilities().find(
      (item) => item.id === input.facilityId && item.published,
    );
    if (!facility?.services.some((item) => item.id === input.serviceId && item.accepting))
      return '';
    if (
      !Number.isFinite(Date.parse(input.preferredTime)) ||
      Date.parse(input.preferredTime) <= Date.now()
    )
      return '';
    if (input.slotId) {
      const slot = this.slots().find(
        (s) => s.id === input.slotId && s.facilityId === input.facilityId,
      );
      if (!slot || !slot.active || slot.bookedCount >= slot.capacity) {
        return '';
      }
      this.bookSlot(input.slotId);
    }
    const now = new Date().toISOString();
    const id = `TV-${new Date().getFullYear()}-${String(128 + this.requests().length).padStart(4, '0')}`;
    const newReq: CareRequest = {
      ...input,
      id,
      status: 'SUBMITTED',
      version: 1,
      updatedAt: now,
      consentAt: now,
      history: [
        {
          status: 'SUBMITTED',
          at: now,
          message: '',
          actor: 'family',
          scheduledTime: input.preferredTime,
        },
      ],
    };
    this.requests.update((items) => [newReq, ...items]);
    this.submittedKeys.set(key, id);
    return id;
  }

  act(id: string, version: number, action: CareAction, staff: boolean, message = '', time = '') {
    const item = this.requests().find((request) => request.id === id);
    if (!item || item.version !== version) return 'CONFLICT';
    if (!careAllowedActions(item, staff).includes(action)) return 'ACTION';
    if (['DECLINE', 'CANCEL', 'PROPOSE_SCHEDULE'].includes(action) && !message.trim())
      return 'REASON';
    const proposedTime = action === 'PROPOSE_SCHEDULE' ? careUtc(time) : item.proposedTime;
    const confirmedTime =
      action === 'ACCEPT_SCHEDULE'
        ? item.proposedTime
        : action === 'CONFIRM_PREFERRED'
          ? item.preferredTime
          : item.confirmedTime;
    if (action === 'PROPOSE_SCHEDULE' && (!proposedTime || Date.parse(proposedTime) <= Date.now()))
      return 'FUTURE';
    if (
      ['CONFIRM_PREFERRED', 'ACCEPT_SCHEDULE'].includes(action) &&
      (!Number.isFinite(Date.parse(confirmedTime)) || Date.parse(confirmedTime) <= Date.now())
    )
      return 'FUTURE';
    const targets: Record<CareAction, CareStatus> = {
      START_REVIEW: 'IN_REVIEW',
      CONFIRM_PREFERRED: 'CONFIRMED',
      PROPOSE_SCHEDULE: 'SCHEDULE_PROPOSED',
      ACCEPT_SCHEDULE: 'CONFIRMED',
      DECLINE: 'DECLINED',
      CANCEL: 'CANCELLED',
      COMPLETE: 'COMPLETED',
    };
    if (['DECLINE', 'CANCEL'].includes(action) && item.slotId) {
      this.releaseSlot(item.slotId);
    }
    const now = new Date().toISOString();
    const status = targets[action];
    this.requests.update((items) =>
      items.map((request) =>
        request.id === id
          ? {
              ...request,
              status,
              proposedTime,
              confirmedTime,
              version: request.version + 1,
              updatedAt: now,
              history: [
                ...request.history,
                {
                  status,
                  at: now,
                  message: message.trim(),
                  actor: staff ? 'staff' : 'family',
                  ...([
                    'PROPOSE_SCHEDULE',
                    'CONFIRM_PREFERRED',
                    'ACCEPT_SCHEDULE',
                    'COMPLETE',
                  ].includes(action)
                    ? {
                        scheduledTime: action === 'PROPOSE_SCHEDULE' ? proposedTime : confirmedTime,
                      }
                    : {}),
                },
              ],
            }
          : request,
      ),
    );
    return '';
  }

  saveFacility(facility: CareFacility) {
    this.facilities.update((items) =>
      items.some((item) => item.id === facility.id)
        ? items.map((item) => (item.id === facility.id ? structuredClone(facility) : item))
        : [...items, structuredClone(facility)],
    );
  }

  recommend(criteria: CareRecommendationCriteria): CareRecommendation[] {
    const api = this.api;
    if (!api || this.fixture) {
      const results = computeCareRecommendations(this.facilities(), criteria);
      this.recommendations.set(results);
      return results;
    }
    this.recommendations.set([]);
    this.error.set('');
    api.fetchRecommendations(criteria).subscribe({
      next: (results) => this.recommendations.set(results),
      error: (error: HttpErrorResponse) => this.setError(error),
      complete: () => {},
    });
    return [];
  }

  toggleCompare(facilityId: string): boolean {
    const current = this.compareIds();
    if (current.includes(facilityId)) {
      this.compareIds.set(current.filter((id) => id !== facilityId));
      return true;
    }
    if (current.length >= 3) {
      return false;
    }
    this.compareIds.set([...current, facilityId]);
    return true;
  }

  setCompareIds(ids: string[]) {
    const valid = ids
      .filter((id) => this.facilities().some((f) => f.id === id && f.published))
      .slice(0, 3);
    this.compareIds.set(Array.from(new Set(valid)));
  }

  clearCompare() {
    this.compareIds.set([]);
  }

  canCompareServicePrice(facilities: CareFacility[], serviceId: CareServiceId): boolean {
    const units = new Set<string>();
    for (const f of facilities) {
      const svc = f.services.find((s) => s.id === serviceId && s.price > 0);
      if (svc) {
        units.add(svc.unit);
      }
    }
    return units.size <= 1;
  }

  slotsForFacility(facilityId: string): CareConsultSlot[] {
    return this.slots().filter((slot) => slot.facilityId === facilityId && slot.active);
  }

  bookSlot(slotId: string): boolean {
    const target = this.slots().find((s) => s.id === slotId && s.active);
    if (!target || target.bookedCount >= target.capacity) {
      return false;
    }
    this.slots.update((items) =>
      items.map((s) => (s.id === slotId ? { ...s, bookedCount: s.bookedCount + 1 } : s)),
    );
    return true;
  }

  releaseSlot(slotId: string) {
    this.slots.update((items) =>
      items.map((s) =>
        s.id === slotId ? { ...s, bookedCount: Math.max(0, s.bookedCount - 1) } : s,
      ),
    );
  }

  submitFeedback(
    requestId: string,
    rating: number,
    tags: string[],
    comment: string,
  ): CareFeedbackItem | false {
    const req = this.requests().find((r) => r.id === requestId);
    if (!req || req.status !== 'COMPLETED') return false;
    if (rating < 1 || rating > 5 || !Number.isInteger(rating)) return false;
    if (this.feedbacks().some((fb) => fb.requestId === requestId)) return false;

    const item: CareFeedbackItem = {
      id: `fb-${Date.now()}-${this.feedbacks().length + 1}`,
      requestId,
      facilityId: req.facilityId,
      rating,
      tags: [...tags],
      comment: comment.trim(),
      moderationStatus: 'pending',
      createdAt: new Date().toISOString(),
    };
    this.feedbacks.update((items) => [item, ...items]);
    return item;
  }

  moderateFeedback(feedbackId: string, status: 'approved' | 'rejected'): boolean {
    const existing = this.feedbacks().find((fb) => fb.id === feedbackId);
    if (!existing) return false;
    this.feedbacks.update((items) =>
      items.map((fb) => (fb.id === feedbackId ? { ...fb, moderationStatus: status } : fb)),
    );
    const approved = this.feedbacks().filter(
      (fb) => fb.facilityId === existing.facilityId && fb.moderationStatus === 'approved',
    );
    const avg =
      approved.length > 0
        ? Math.round((approved.reduce((sum, fb) => sum + fb.rating, 0) / approved.length) * 10) / 10
        : 0;
    this.facilities.update((items) =>
      items.map((f) =>
        f.id === existing.facilityId
          ? { ...f, averageRating: avg, feedbackCount: approved.length }
          : f,
      ),
    );
    return true;
  }

  feedbackForFacility(facilityId: string, includePending = false): CareFeedbackItem[] {
    return this.feedbacks().filter(
      (fb) =>
        fb.facilityId === facilityId && (includePending || fb.moderationStatus === 'approved'),
    );
  }
}
