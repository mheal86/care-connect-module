import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Injectable, InjectionToken, inject } from '@angular/core';
import { Observable, map, of } from 'rxjs';
import { apiUrl, HTTP_OPTS } from './api.config';
import {
  CareAction,
  CareConsultSlot,
  CareFacility,
  CareFeedbackItem,
  CareRecommendation,
  CareRecommendationCriteria,
  CareRequest,
  CareServiceId,
  CareStatus,
  computeCareRecommendations,
} from '../../features/care-connect/care-connect.model';

export interface CareConnectMeResponse {
  userId: string;
  role: 'family' | 'staff';
  facilityIds: string[];
  managerIds: string[];
  profiles: { id: string; name: string }[];
}
export interface CareConnectApi {
  mode: 'http' | 'fixture';
  getMe(): Observable<CareConnectMeResponse | false>;
  fetchFacilities(): Observable<CareFacility[]>;
  fetchRequests(scope: 'mine' | 'inbox'): Observable<CareRequest[]>;
  createRequest(
    input: Omit<CareRequest, 'id' | 'status' | 'version' | 'updatedAt' | 'history' | 'consentAt'>,
    idempotencyKey: string,
  ): Observable<CareRequest | false>;
  actOnRequest(
    requestId: string,
    expectedVersion: number,
    action: CareAction,
    message: string,
    proposedTime: string,
    staff?: boolean,
  ): Observable<CareRequest | false>;
  saveFacility(facility: CareFacility): Observable<CareFacility | false>;
  fetchRecommendations(criteria: CareRecommendationCriteria): Observable<CareRecommendation[]>;
  listSlots(facilityId: string): Observable<CareConsultSlot[]>;
  listFeedback(facilityId: string): Observable<CareFeedbackItem[]>;
  submitFeedback(
    requestId: string,
    rating: number,
    tags: string[],
    comment: string,
  ): Observable<CareFeedbackItem | false>;
  moderateFeedback(
    feedbackId: string,
    status: 'approved' | 'rejected',
  ): Observable<CareFeedbackItem | false>;
}
export interface CareServiceDto {
  id: string;
  name: string;
  category: string;
  uiId: CareServiceId;
  price: number;
  priceUnit: 'month' | 'day' | 'session';
  accepting: boolean;
}
export interface CareFacilityDto {
  id: string;
  name: string;
  type: string;
  region: string;
  address: string;
  description: string;
  phone: string;
  services: CareServiceDto[];
  published: boolean;
  updatedAt: string;
  amenities: string[];
  highlights: string[];
  lat: number;
  lng: number;
  geoVerified: boolean;
  verifiedBadge: boolean;
  suitableFor: ('L1' | 'L2' | 'L3')[];
  supportTags: string[];
  distanceKm: number;
  averageRating: number;
  feedbackCount: number;
}
export interface CareRequestDto {
  id: string;
  code: string;
  facilityId: string;
  serviceId: string;
  profileId: string;
  profileName: string;
  facilityName: string;
  serviceName: string;
  contactName: string;
  contactPhone: string;
  careNeeds: string;
  note: string;
  preferredSlot: string;
  proposedSlot: string;
  confirmedSlot: string;
  status: string;
  version: number;
  updatedAt: string;
  createdAt: string;
  slotId: string;
  reminderOptIn: boolean;
  events: { toStatus: string; at: string; note: string; actorRole: string; slot: string }[];
}
export interface CareFeedbackDto extends CareFeedbackItem {}
export interface CareMeDto {
  username: string;
  memberFacilities: { facilityId: string; memberRole: string }[];
  profiles: { id: string; name: string }[];
}
const STATUS_MAP: Record<string, CareStatus> = {
  PENDING: 'SUBMITTED',
  IN_REVIEW: 'IN_REVIEW',
  RESCHEDULE_PROPOSED: 'SCHEDULE_PROPOSED',
  CONFIRMED: 'CONFIRMED',
  REJECTED: 'DECLINED',
  CANCELLED: 'CANCELLED',
  COMPLETED: 'COMPLETED',
};
const ACTION_MAP: Record<CareAction, string> = {
  START_REVIEW: 'start_review',
  CONFIRM_PREFERRED: 'confirm',
  PROPOSE_SCHEDULE: 'propose_slot',
  ACCEPT_SCHEDULE: 'accept_slot',
  DECLINE: 'reject',
  CANCEL: 'cancel',
  COMPLETE: 'complete',
};
export const CARE_CONNECT_API = new InjectionToken<CareConnectApi>('CARE_CONNECT_API');
@Injectable({ providedIn: 'root' })
export class CareConnectHttpApi implements CareConnectApi {
  mode: 'http' | 'fixture' = 'http';
  http = inject(HttpClient);
  profileNames = new Map<string, string>();
  serviceIds = new Map<string, string>();
  serviceTypes = new Map<string, CareServiceId>();
  toFacility(dto: CareFacilityDto): CareFacility {
    const services = dto.services
      .filter((s, i, all) => all.findIndex((t) => t.uiId === s.uiId) === i)
      .map((s) => {
        const id =
          s.uiId ||
          (s.category === 'stay' ? 'longstay' : s.category === 'day' ? 'daycare' : 'rehab');
        this.serviceIds.set(`${dto.id}:${id}`, s.id);
        this.serviceTypes.set(s.id, id);
        return { id, price: s.price, unit: s.priceUnit, accepting: s.accepting !== false };
      });
    return {
      ...dto,
      key: '',
      addressKey: '',
      descriptionKey: '',
      type:
        (
          {
            nursing_home: 'residential',
            day_care: 'daycare',
            rehab: 'health',
            home_care: 'health',
          } as Record<string, string>
        )[dto.type] || 'health',
      region: dto.region || 'hcm',
      services,
      customName: dto.name,
      customAddress: dto.address,
      customDescription: dto.description || dto.highlights.join('. '),
      contact: dto.phone,
      amenities: dto.amenities || [],
      published: dto.published !== false,
    };
  }
  toRequest(dto: CareRequestDto): CareRequest {
    return {
      ...dto,
      code: dto.code,
      facilityLabel: dto.facilityName,
      profileLabel: dto.profileName === dto.profileId ? '' : dto.profileName,
      serviceLabel: dto.serviceName,
      serviceId: this.serviceTypes.get(dto.serviceId) || 'longstay',
      profile: dto.profileId,
      phone: dto.contactPhone,
      needs: dto.careNeeds,
      preferredTime: dto.preferredSlot,
      proposedTime: dto.proposedSlot || '',
      confirmedTime: dto.confirmedSlot || '',
      status: STATUS_MAP[dto.status] || 'SUBMITTED',
      consentAt: dto.createdAt,
      history: dto.events.map((e) => ({
        status: STATUS_MAP[e.toStatus] || 'SUBMITTED',
        at: e.at,
        message: e.note,
        actor: e.actorRole === 'staff' ? 'staff' : 'family',
        ...(e.slot ? { scheduledTime: e.slot } : {}),
      })),
    };
  }
  getMe(): Observable<CareConnectMeResponse> {
    return this.http
      .get<CareMeDto>(apiUrl('/api/care/me'), HTTP_OPTS)
      .pipe(
        map((dto) => ({
          userId: dto.username,
          role: dto.memberFacilities.length ? 'staff' : 'family',
          facilityIds: dto.memberFacilities.map((m) => m.facilityId),
          managerIds: dto.memberFacilities
            .filter((m) => m.memberRole === 'manager')
            .map((m) => m.facilityId),
          profiles: (dto.profiles || []).map((profile) => {
            this.profileNames.set(profile.id, profile.name);
            return profile;
          }),
        })),
      );
  }
  fetchFacilities(): Observable<CareFacility[]> {
    return this.http
      .get<{ facilities: CareFacilityDto[] }>(apiUrl('/api/care/facilities'), HTTP_OPTS)
      .pipe(map((res) => res.facilities.map((f) => this.toFacility(f))));
  }
  fetchRequests(scope: 'mine' | 'inbox'): Observable<CareRequest[]> {
    return this.http
      .get<{
        requests: CareRequestDto[];
      }>(apiUrl(`/api/care/requests?scope=${scope === 'inbox' ? 'facility' : 'mine'}`), HTTP_OPTS)
      .pipe(map((res) => res.requests.map((r) => this.toRequest(r))));
  }
  createRequest(
    input: Omit<CareRequest, 'id' | 'status' | 'version' | 'updatedAt' | 'history' | 'consentAt'>,
    idempotencyKey: string,
  ): Observable<CareRequest> {
    const body = {
      facilityId: input.facilityId,
      serviceId: this.serviceIds.get(`${input.facilityId}:${input.serviceId}`) || input.serviceId,
      profileId: input.profile,
      profileName: this.profileNames.get(input.profile) || input.profile,
      careNeeds: input.needs,
      contactName: input.contactName,
      contactPhone: input.phone,
      preferredSlot: input.preferredTime,
      note: input.note,
      slotId: input.slotId || '',
      reminderOptIn: input.reminderOptIn || false,
      consent: true,
    };
    return this.http
      .post<{
        request: CareRequestDto;
      }>(apiUrl('/api/care/requests'), body, { ...HTTP_OPTS, headers: new HttpHeaders({ 'Idempotency-Key': idempotencyKey }) })
      .pipe(map((res) => this.toRequest(res.request)));
  }
  actOnRequest(
    id: string,
    expectedVersion: number,
    action: CareAction,
    message: string,
    proposedTime: string,
    staff = false,
  ): Observable<CareRequest> {
    return this.http
      .post<{
        request: CareRequestDto;
      }>(apiUrl(`/api/care/requests/${encodeURIComponent(id)}/actions`), { action: action === 'CANCEL' && staff ? 'staff_cancel' : ACTION_MAP[action], expectedVersion, note: message, proposedSlot: proposedTime || '' }, HTTP_OPTS)
      .pipe(map((res) => this.toRequest(res.request)));
  }
  saveFacility(f: CareFacility): Observable<CareFacility> {
    const body = {
      name: f.customName,
      address: f.customAddress,
      description: f.customDescription,
      phone: f.contact || '',
      facility_type: (
        { residential: 'nursing_home', daycare: 'day_care', health: 'rehab' } as Record<
          string,
          string
        >
      )[f.type],
      region: f.region,
      published: f.published,
      amenities: f.amenities,
      services: f.services.map((s) => ({
        id: `${f.id}-${s.id}`,
        name:
          s.id === 'longstay'
            ? 'Chăm sóc dài hạn'
            : s.id === 'daycare'
              ? 'Chăm sóc ban ngày'
              : 'Phục hồi chức năng',
        category: s.id === 'longstay' ? 'stay' : s.id === 'daycare' ? 'day' : 'rehab',
        ui_id: s.id,
        price: s.price,
        price_unit: s.unit,
        accepting: s.accepting,
      })),
    };
    return this.http
      .put<{
        facility: CareFacilityDto;
      }>(apiUrl(`/api/care/catalog/facilities/${encodeURIComponent(f.id)}`), body, HTTP_OPTS)
      .pipe(map((res) => this.toFacility(res.facility)));
  }
  fetchRecommendations(c: CareRecommendationCriteria): Observable<CareRecommendation[]> {
    return this.http
      .post<{
        recommendations: {
          facilityId: string;
          score: number;
          reasons: string[];
          missing: string[];
        }[];
      }>(apiUrl('/api/care/recommendations'), { careLevel: c.supportLevel || 'L1', requiredTags: c.priorityTags, budgetMax: c.budgetMaxVnd, budgetUnit: c.serviceId === 'daycare' ? 'day' : c.serviceId === 'rehab' ? 'session' : 'month', preferredRegion: c.region, serviceType: c.serviceId }, HTTP_OPTS)
      .pipe(
        map((res) =>
          res.recommendations.map((r) => ({
            facilityId: r.facilityId,
            score: r.score,
            reasons: r.reasons.map((t, i) => ({ code: `REMOTE_${i}`, weight: 0, matchedValue: t })),
            missing: [],
            missingDescriptions: r.missing,
            rulesVersion: 'care-rec-v1' as const,
          })),
        ),
      );
  }
  listSlots(id: string): Observable<CareConsultSlot[]> {
    return this.http
      .get<{
        slots: CareConsultSlot[];
      }>(apiUrl(`/api/care/facilities/${encodeURIComponent(id)}/slots`), HTTP_OPTS)
      .pipe(map((res) => res.slots.map((s) => ({ ...s, active: true }))));
  }
  listFeedback(id: string): Observable<CareFeedbackItem[]> {
    return this.http
      .get<{
        feedback: CareFeedbackItem[];
      }>(apiUrl(`/api/care/facilities/${encodeURIComponent(id)}/feedback?include_unapproved=true`), HTTP_OPTS)
      .pipe(map((res) => res.feedback));
  }
  submitFeedback(
    id: string,
    rating: number,
    tags: string[],
    comment: string,
  ): Observable<CareFeedbackItem> {
    return this.http
      .post<{
        feedback: CareFeedbackItem;
      }>(apiUrl(`/api/care/requests/${encodeURIComponent(id)}/feedback`), { rating, tags, comment }, HTTP_OPTS)
      .pipe(map((res) => res.feedback));
  }
  moderateFeedback(
    id: string,
    moderationStatus: 'approved' | 'rejected',
  ): Observable<CareFeedbackItem> {
    return this.http
      .patch<{
        feedback: CareFeedbackItem;
      }>(apiUrl(`/api/care/feedback/${encodeURIComponent(id)}/moderation`), { moderationStatus }, HTTP_OPTS)
      .pipe(map((res) => res.feedback));
  }
}
@Injectable({ providedIn: 'root' })
export class CareConnectFixtureApi implements CareConnectApi {
  mode: 'http' | 'fixture' = 'fixture';
  getMe() {
    return of({
      userId: 'demo-family',
      role: 'family' as const,
      facilityIds: ['an-nhien'],
      managerIds: [],
      profiles: [],
    });
  }
  fetchFacilities() {
    return of<CareFacility[]>([]);
  }
  fetchRequests() {
    return of<CareRequest[]>([]);
  }
  createRequest() {
    return of(false as const);
  }
  actOnRequest() {
    return of(false as const);
  }
  saveFacility(facility: CareFacility) {
    return of(facility);
  }
  fetchRecommendations(criteria: CareRecommendationCriteria) {
    return of(computeCareRecommendations([], criteria));
  }
  listSlots() {
    return of<CareConsultSlot[]>([]);
  }
  listFeedback() {
    return of<CareFeedbackItem[]>([]);
  }
  submitFeedback() {
    return of(false as const);
  }
  moderateFeedback() {
    return of(false as const);
  }
}
