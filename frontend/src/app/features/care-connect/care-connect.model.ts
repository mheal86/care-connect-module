export type CareView =
  | 'facilities'
  | 'facility'
  | 'consult'
  | 'requests'
  | 'request'
  | 'inbox'
  | 'catalog'
  | 'extensions';
export type CareStatus =
  | 'SUBMITTED'
  | 'IN_REVIEW'
  | 'SCHEDULE_PROPOSED'
  | 'CONFIRMED'
  | 'DECLINED'
  | 'CANCELLED'
  | 'COMPLETED';
export type CareAction =
  | 'START_REVIEW'
  | 'CONFIRM_PREFERRED'
  | 'PROPOSE_SCHEDULE'
  | 'ACCEPT_SCHEDULE'
  | 'DECLINE'
  | 'CANCEL'
  | 'COMPLETE';
export type CareServiceId = 'longstay' | 'daycare' | 'rehab';
export type CareSupportLevel = 'L1' | 'L2' | 'L3';

export interface CareService {
  id: CareServiceId;
  price: number;
  unit: 'month' | 'day' | 'session';
  accepting: boolean;
}
export interface CareFacility {
  id: string;
  key: string;
  region: string;
  type: string;
  addressKey: string;
  descriptionKey: string;
  services: CareService[];
  published: boolean;
  updatedAt: string;
  amenities: string[];
  customName?: string;
  customAddress?: string;
  customDescription?: string;
  contact?: string;
  lat?: number;
  lng?: number;
  geoVerified?: boolean;
  verifiedBadge?: boolean;
  suitableFor?: CareSupportLevel[];
  supportTags?: string[];
  distanceKm?: number;
  averageRating?: number;
  feedbackCount?: number;
}
export interface CareHistory {
  status: CareStatus;
  at: string;
  message: string;
  actor: 'family' | 'staff';
  scheduledTime?: string;
}
export interface CareRequest {
  id: string;
  code?: string;
  facilityLabel?: string;
  profileLabel?: string;
  serviceLabel?: string;
  facilityId: string;
  serviceId: CareServiceId;
  profile: string;
  contactName: string;
  phone: string;
  needs: string;
  note: string;
  preferredTime: string;
  proposedTime: string;
  confirmedTime: string;
  status: CareStatus;
  version: number;
  updatedAt: string;
  consentAt: string;
  history: CareHistory[];
  slotId?: string;
  reminderOptIn?: boolean;
}
export interface CareFilters {
  q: string;
  region: string;
  type: string;
  service: string;
}

export interface CareRecommendationCriteria {
  region: string;
  serviceId: string;
  supportLevel: string;
  budgetMaxVnd: number;
  priorityTags: string[];
}

export interface CareRecommendationReason {
  code: string;
  weight: number;
  matchedValue: string;
}

export interface CareRecommendation {
  facilityId: string;
  score: number;
  reasons: CareRecommendationReason[];
  missing: string[];
  missingDescriptions?: string[];
  rulesVersion: 'care-rec-v1';
}

export interface CareConsultSlot {
  id: string;
  facilityId: string;
  startsAt: string;
  endsAt: string;
  capacity: number;
  bookedCount: number;
  active: boolean;
}

export interface CareFeedbackItem {
  id: string;
  requestId: string;
  facilityId: string;
  rating: number;
  tags: string[];
  comment: string;
  moderationStatus: 'pending' | 'approved' | 'rejected';
  createdAt: string;
}

export const CARE_STATUSES: CareStatus[] = [
  'SUBMITTED',
  'IN_REVIEW',
  'SCHEDULE_PROPOSED',
  'CONFIRMED',
  'COMPLETED',
  'DECLINED',
  'CANCELLED',
];
export const CARE_SERVICES: CareServiceId[] = ['longstay', 'daycare', 'rehab'];
export const CARE_SUPPORT_LEVELS: CareSupportLevel[] = ['L1', 'L2', 'L3'];
export const CARE_PRIORITY_TAGS: string[] = ['nursing', 'rehab', 'garden', 'accessible', 'family'];
export const CARE_FEEDBACK_TAGS: string[] = ['DEDICATED', 'CLEAN', 'CLEAR_INFO', 'ON_TIME'];
export const STAFF_FACILITY_ID = 'an-nhien';

/** Fixed Vietnam wall time, independent of the device time zone. */
export function careLocalDate(offset: number, hour = 9) {
  const now = new Date();
  now.setUTCDate(now.getUTCDate() + offset);
  return `${new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Ho_Chi_Minh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)}T${String(hour).padStart(2, '0')}:00`;
}

export function careUtc(local: string) {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(local)) return '';
  const date = new Date(`${local}:00+07:00`);
  if (!Number.isFinite(date.getTime())) return '';
  const wallTime = new Date(date.getTime() + 7 * 60 * 60 * 1000).toISOString().slice(0, 16);
  return wallTime === local ? date.toISOString() : '';
}

export function careSearchText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd')
    .replace(/Đ/g, 'D')
    .toLowerCase();
}

export function careAllowedActions(request: CareRequest, staff: boolean): CareAction[] {
  if (['CANCELLED', 'DECLINED', 'COMPLETED'].includes(request.status)) return [];
  if (!staff)
    return request.status === 'SCHEDULE_PROPOSED' ? ['ACCEPT_SCHEDULE', 'CANCEL'] : ['CANCEL'];
  if (request.facilityId !== STAFF_FACILITY_ID) return [];
  switch (request.status) {
    case 'SUBMITTED':
      return ['START_REVIEW', 'CANCEL'];
    case 'IN_REVIEW':
      return ['CONFIRM_PREFERRED', 'PROPOSE_SCHEDULE', 'DECLINE', 'CANCEL'];
    case 'SCHEDULE_PROPOSED':
      return ['PROPOSE_SCHEDULE', 'DECLINE', 'CANCEL'];
    case 'CONFIRMED':
      return Date.parse(request.confirmedTime) <= Date.now() ? ['COMPLETE', 'CANCEL'] : ['CANCEL'];
    default:
      return [];
  }
}

/** Rule-based explainable recommendation engine (care-rec-v1). Non-clinical decision support. */
export function computeCareRecommendations(
  facilities: CareFacility[],
  criteria: CareRecommendationCriteria,
): CareRecommendation[] {
  const results: CareRecommendation[] = [];
  for (const facility of facilities) {
    if (!facility.published) continue;
    let score = 0;
    const reasons: CareRecommendationReason[] = [];
    const missing: string[] = [];

    // 1. Region match (weight 30)
    if (criteria.region) {
      if (facility.region === criteria.region) {
        score += 30;
        reasons.push({ code: 'MATCH_REGION', weight: 30, matchedValue: facility.region });
      } else {
        missing.push('REGION_MISMATCH');
      }
    } else {
      score += 30;
      reasons.push({ code: 'MATCH_REGION', weight: 30, matchedValue: facility.region });
    }

    // 2. Service accepting (weight 25)
    let matchedService: CareService | false = false;
    if (criteria.serviceId) {
      matchedService =
        facility.services.find((s) => s.id === criteria.serviceId && s.accepting) || false;
      if (matchedService !== false) {
        score += 25;
        reasons.push({ code: 'MATCH_SERVICE', weight: 25, matchedValue: matchedService.id });
      } else {
        missing.push('SERVICE_UNAVAILABLE');
      }
    } else {
      matchedService = facility.services.find((s) => s.accepting) || false;
      if (matchedService !== false) {
        score += 25;
        reasons.push({ code: 'MATCH_SERVICE', weight: 25, matchedValue: matchedService.id });
      } else {
        missing.push('SERVICE_UNAVAILABLE');
      }
    }

    // 3. Support level suitability (weight 20)
    const suitable = facility.suitableFor || ['L1', 'L2'];
    if (criteria.supportLevel) {
      if (suitable.includes(criteria.supportLevel as CareSupportLevel)) {
        score += 20;
        reasons.push({
          code: 'MATCH_SUPPORT_LEVEL',
          weight: 20,
          matchedValue: criteria.supportLevel,
        });
      } else {
        missing.push('SUPPORT_LEVEL_MISMATCH');
      }
    } else {
      score += 20;
      reasons.push({
        code: 'MATCH_SUPPORT_LEVEL',
        weight: 20,
        matchedValue: suitable.join(','),
      });
    }

    // 4. Budget (weight 15). Price === 0 means unpublished, NEVER free!
    const refService = matchedService !== false ? matchedService : facility.services[0];
    if (!refService || refService.price <= 0) {
      missing.push('BUDGET_NOT_PUBLISHED');
    } else if (criteria.budgetMaxVnd > 0) {
      if (refService.price <= criteria.budgetMaxVnd) {
        score += 15;
        reasons.push({
          code: 'WITHIN_BUDGET',
          weight: 15,
          matchedValue: String(refService.price),
        });
      } else {
        missing.push('OVER_BUDGET');
      }
    } else {
      score += 15;
      reasons.push({
        code: 'WITHIN_BUDGET',
        weight: 15,
        matchedValue: String(refService.price),
      });
    }

    // 5. Priority tags / amenities (weight 10)
    const facilityTags = new Set([...(facility.amenities || []), ...(facility.supportTags || [])]);
    if (criteria.priorityTags.length > 0) {
      const matchedTags = criteria.priorityTags.filter((tag) => facilityTags.has(tag));
      if (matchedTags.length > 0) {
        const tagScore = Math.round((10 * matchedTags.length) / criteria.priorityTags.length);
        score += tagScore;
        reasons.push({
          code: 'MATCH_TAGS',
          weight: tagScore,
          matchedValue: matchedTags.join(','),
        });
      }
      for (const tag of criteria.priorityTags) {
        if (!facilityTags.has(tag)) {
          missing.push(`MISSING_TAG_${tag.toUpperCase()}`);
        }
      }
    } else {
      score += 10;
      reasons.push({
        code: 'MATCH_TAGS',
        weight: 10,
        matchedValue: Array.from(facilityTags).slice(0, 3).join(','),
      });
    }

    results.push({
      facilityId: facility.id,
      score,
      reasons,
      missing,
      rulesVersion: 'care-rec-v1',
    });
  }

  return results.sort((a, b) => b.score - a.score || a.facilityId.localeCompare(b.facilityId));
}
