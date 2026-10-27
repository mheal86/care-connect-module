import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { CareConnectHttpApi, CareRequestDto } from './care-connect.service';

function requestDto(): CareRequestDto {
  return {id:'req-test',code:'CC-test',facilityId:'an-nhien',serviceId:'an-nhien-longstay',profileId:'elder_demo',profileName:'elder_demo',facilityName:'Cơ sở mẫu',serviceName:'Chăm sóc dài hạn',contactName:'Liên hệ mẫu',contactPhone:'0900000000',careNeeds:'Nhu cầu tư vấn mẫu',note:'',preferredSlot:'2026-11-01T09:00:00Z',proposedSlot:'',confirmedSlot:'',status:'PENDING',version:1,updatedAt:'2026-10-28T00:00:00Z',createdAt:'2026-10-28T00:00:00Z',slotId:'',reminderOptIn:false,events:[]};
}

describe('Care request profile display', () => {
  beforeEach(() => { TestBed.configureTestingModule({providers:[provideHttpClient(),provideHttpClientTesting(),CareConnectHttpApi]}); });
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('uses the linked profile name when creating a request', () => {
    const api=TestBed.inject(CareConnectHttpApi);const http=TestBed.inject(HttpTestingController);
    api.getMe().subscribe();
    http.expectOne('/api/care/me').flush({username:'family_demo',memberFacilities:[],profiles:[{id:'elder_demo',name:'Người cao tuổi mẫu'}]});
    api.createRequest({facilityId:'an-nhien',serviceId:'longstay',profile:'elder_demo',contactName:'Liên hệ mẫu',phone:'0900000000',needs:'Nhu cầu tư vấn mẫu',note:'',preferredTime:'2026-11-01T09:00:00Z',proposedTime:'',confirmedTime:''},'name-check').subscribe();
    const req=http.expectOne('/api/care/requests');
    expect(req.request.body.profileId).toBe('elder_demo');
    expect(req.request.body.profileName).toBe('Người cao tuổi mẫu');
    req.flush({request:{...requestDto(),profileName:'Người cao tuổi mẫu'}});
  });

  it('lets the UI resolve older records that stored the profile identifier as the name', () => {
    const api=TestBed.inject(CareConnectHttpApi);
    expect(api.toRequest(requestDto()).profileLabel).toBe('');
    expect(api.toRequest({...requestDto(),profileName:'Tên hồ sơ đã lưu'}).profileLabel).toBe('Tên hồ sơ đã lưu');
  });
});
