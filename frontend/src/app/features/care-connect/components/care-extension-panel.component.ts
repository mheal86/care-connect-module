import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ButtonModule } from 'primeng/button';
import { SelectModule } from 'primeng/select';
import { firstValueFrom } from 'rxjs';
import { apiUrl, HTTP_OPTS } from '../../../core/api/api.config';
import { TranslatePipe } from '../../../shared/pipes/translate.pipe';
import { CareConnectStore } from '../care-connect.store';
export interface CareTrialAlert {
  id: string;
  profile_id: string;
  profile_name?: string;
  created_by: string;
  source: string;
  note: string;
  status: string;
  acknowledged_by: string;
  created_at: string;
}
export interface CareProfileGrant {
  id: string;
  profile_id: string;
  profile_name?: string;
  owner_id: string;
  facility_id: string;
  fields: string[];
  revoked_at: string;
  expires_at: string;
}
export interface CareExtensionOverview {
  userId: string;
  caregiver: boolean;
  profiles: { id: string; name: string }[];
  alerts: CareTrialAlert[];
  grants: CareProfileGrant[];
  accesses: { id: number; grant_id: string; actor_id: string; action: string; at: string }[];
  games: { id: string; status: string; ply_count: number; created_at: string; outcome: string }[];
}
export interface SharedCareProfile {
  profileId: string;
  fields: { supportNeeds?: string; contact?: string; dailyRoutine?: string };
  updatedAt: string;
  expiresAt: string;
}
@Component({
  selector: 'app-care-extension-panel',
  standalone: true,
  imports: [FormsModule, ButtonModule, SelectModule, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<header class="extension-heading">
      <h1>{{ 'CARE.EXT.TITLE' | translate }}</h1>
      <p>{{ 'CARE.EXT.INTRO' | translate }}</p>
    </header>
    @if (error()) {
      <p class="extension-error" role="alert">{{ 'CARE.API_ERROR' | translate }}</p>
    }
    @if (notice()) {
      <p role="status">{{ 'CARE.EXT.SAVED' | translate }}</p>
    }
    @if (loading() && !data()) {
      <section aria-busy="true">
        <p role="status">{{ 'CARE.LOADING' | translate }}</p>
      </section>
    }
    @if (data(); as overview) {
      <div class="extension-grid">
        @if (overview.profiles.length > 0) {
        <section>
          <h2>{{ 'CARE.EXT.SOS_TITLE' | translate }}</h2>
          <p class="extension-note">{{ 'CARE.EXT.SOS_NOTE' | translate }}</p>
          <label for="extension-profile">{{ 'CARE.PROFILE_LABEL' | translate }}</label
          ><p-select
            appendTo="body"
            inputId="extension-profile"
            [options]="overview.profiles"
            optionLabel="name"
            optionValue="id"
            [(ngModel)]="profileId"
            (onChange)="consent = false"
          />
          <label for="sos-note">{{ 'CARE.EXT.ALERT_NOTE' | translate }}</label
          ><textarea id="sos-note" [(ngModel)]="alertNote" rows="3" maxlength="1000"></textarea>
          <div class="extension-actions">
            <p-button
              [label]="'CARE.EXT.SEND_SOS' | translate"
              [ariaLabel]="'CARE.EXT.SEND_SOS' | translate"
              icon="pi pi-bell"
              [disabled]="busy() || alertNote.trim().length < 5 || !profileId"
              (onClick)="sendAlert('manual')"
            /><p-button
              [label]="'CARE.EXT.SIMULATE' | translate"
              [ariaLabel]="'CARE.EXT.SIMULATE' | translate"
              [outlined]="true"
              [disabled]="busy() || alertNote.trim().length < 5 || !profileId"
              (onClick)="sendAlert('simulator')"
            />
          </div>
          @for (alert of overview.alerts; track alert.id) {
            <article class="extension-row">
              <div>
                <strong
                  >{{ profileName(alert.profile_id) }} ·
                  {{ 'CARE.EXT.STATUS_' + alert.status | translate }}</strong
                >
                <p>{{ alert.note }}</p>
                <small
                  >{{ date(alert.created_at) }} ·
                  {{ 'CARE.EXT.SOURCE_' + alert.source | translate }}</small
                >
              </div>
              @if (alert.status === 'NEW') {
                <div class="extension-actions">
                  @if (overview.caregiver) {
                    <p-button
                      [label]="'CARE.EXT.ACKNOWLEDGE' | translate"
                      [ariaLabel]="'CARE.EXT.ACKNOWLEDGE' | translate"
                      [text]="true"
                      [disabled]="busy()"
                      (onClick)="actAlert(alert.id, 'acknowledge')"
                    />
                  }
                  @if (alert.created_by === overview.userId) {
                    <p-button
                      [label]="'CARE.EXT.CANCEL_ALERT' | translate"
                      [ariaLabel]="'CARE.EXT.CANCEL_ALERT' | translate"
                      [text]="true"
                      [disabled]="busy()"
                      (onClick)="actAlert(alert.id, 'cancel')"
                    />
                  }
                </div>
              }
            </article>
          }
          @if (!overview.alerts.length) {
            <p>{{ 'CARE.EXT.NO_ALERTS' | translate }}</p>
          }
        </section>
        }
        <section>
          <h2>{{ 'CARE.EXT.SHARE_TITLE' | translate }}</h2>
          <p>{{ 'CARE.EXT.SHARE_NOTE' | translate }}</p>
          @if (overview.profiles.length > 0) {
          <label for="share-facility">{{ 'CARE.EXT.RECIPIENT' | translate }}</label
          ><p-select
            appendTo="body"
            inputId="share-facility"
            [options]="facilityOptions()"
            optionLabel="label"
            optionValue="value"
            [(ngModel)]="facilityId"
            (onChange)="consent = false"
          />
          <fieldset>
            <legend>{{ 'CARE.EXT.SHARED_FIELDS' | translate }}</legend>
            @for (field of fields; track field) {
              <label class="extension-check"
                ><input
                  type="checkbox"
                  [checked]="selectedFields.includes(field)"
                  (change)="toggleField(field)"
                />{{ 'CARE.EXT.FIELD_' + field | translate }}</label
              >
            }
          </fieldset>
          <label class="extension-check"
            ><input type="checkbox" [(ngModel)]="consent" />{{
              'CARE.EXT.CONSENT' | translate
            }}</label
          >
          <p-button
            [label]="'CARE.EXT.SHARE' | translate"
            [ariaLabel]="'CARE.EXT.SHARE' | translate"
            icon="pi pi-share-alt"
            [disabled]="busy() || !consent || !facilityId || !selectedFields.length || !profileId"
            (onClick)="share()"
          />
          }
          @for (grant of overview.grants; track grant.id) {
            <article class="extension-row">
              <div>
                <strong
                  >{{ grant.profile_name || profileName(grant.profile_id) }} →
                  {{ facilityName(grant.facility_id) }}</strong
                >
                <p>{{ 'CARE.EXT.EXPIRES' | translate }}: {{ date(grant.expires_at) }}</p>
                <small>{{
                  (grant.revoked_at ? 'CARE.EXT.REVOKED' : 'CARE.EXT.GRANTED') | translate
                }}</small>
              </div>
              <div class="extension-actions">
                @if (grant.owner_id === overview.userId && !grant.revoked_at) {
                  <p-button
                    [label]="'CARE.EXT.REVOKE' | translate"
                    [ariaLabel]="'CARE.EXT.REVOKE' | translate"
                    [text]="true"
                    [disabled]="busy()"
                    (onClick)="revoke(grant.id)"
                  />
                }
                @if (store.memberIds().includes(grant.facility_id) && !grant.revoked_at) {
                  <p-button
                    [label]="'CARE.EXT.READ_SHARED' | translate"
                    [ariaLabel]="'CARE.EXT.READ_SHARED' | translate"
                    [text]="true"
                    [disabled]="busy()"
                    (onClick)="readShared(grant.id)"
                  />
                }
              </div>
            </article>
          }
          @if (shared(); as profile) {
            <div class="shared-content">
              <h3>{{ 'CARE.EXT.SHARED_CONTENT' | translate }}</h3>
              @for (entry of sharedEntries(profile); track entry.key) {
                <p>
                  <strong>{{ 'CARE.EXT.FIELD_' + entry.key | translate }}:</strong>
                  {{ entry.value }}
                </p>
              }
              <small
                >{{ 'CARE.EXT.FAMILY_SOURCE' | translate }} · {{ date(profile.updatedAt) }}</small
              >
            </div>
          }
          @for (access of overview.accesses.slice(0, 3); track access.id) {
            <p class="access-log">
              {{ 'CARE.EXT.ACCESS_LOG' | translate }}: {{ access.actor_id }} · {{ access.action }} ·
              {{ date(access.at) }}
            </p>
          }
        </section>
      </div>
    }`,
  styles: [
    `
      .extension-heading {
        margin: 24px 0;
      }
      h1 {
        font-size: 32px;
        margin: 0 0 12px;
      }
      h2 {
        font-size: 22px;
        margin: 0 0 12px;
      }
      p {
        line-height: 1.65;
        margin: 8px 0 16px;
      }
      .extension-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 24px;
      }
      section {
        background: var(--admin-surface);
        border: 1px solid var(--admin-border-light);
        border-radius: var(--radius-lg);
        padding: 24px;
        min-width: 0;
      }
      section > label {
        display: block;
        margin-block: 16px 8px;
      }
      textarea {
        width: 100%;
        box-sizing: border-box;
        padding: 12px;
        border-radius: var(--radius-sm);
        border: 1px solid var(--admin-border-light);
        color: var(--admin-text-primary);
        background: var(--admin-surface);
        font-size: 16px;
        resize: vertical;
      }
      fieldset {
        border: 1px solid var(--admin-border-light);
        margin-top: 20px;
        padding: 12px 16px;
      }
      .extension-check {
        display: flex;
        align-items: start;
        gap: 10px;
        min-height: 44px;
        line-height: 1.6;
        margin-block: 8px;
      }
      input[type='checkbox'] {
        width: 20px;
        height: 20px;
        margin-top: 4px;
        accent-color: var(--admin-primary-light-text);
      }
      .extension-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 12px 0;
      }
      .extension-row {
        border-top: 1px solid var(--admin-border-light);
        padding-block: 16px;
        margin-top: 16px;
      }
      small,
      .extension-note,
      .access-log {
        color: var(--admin-text-muted);
        line-height: 1.6;
      }
      .shared-content {
        padding: 16px;
        background: var(--admin-primary-light);
        border-radius: var(--radius-sm);
      }
      .interaction-summary {
        margin-top: 24px;
      }
      .extension-table {
        overflow-x: auto;
      }
      table {
        width: 100%;
        border-collapse: collapse;
        text-align: left;
      }
      th,
      td {
        padding: 14px 12px;
        border-bottom: 1px solid var(--admin-border-light);
      }
      :focus-visible {
        outline: 3px solid var(--admin-primary-light-text);
        outline-offset: 3px;
      }
      ::ng-deep {
        app-care-extension-panel .p-select {
          width: 100%;
          min-height: 44px;
        }
        app-care-extension-panel .p-button {
          min-height: 44px;
          padding: 10px 16px;
          border: 1px solid var(--admin-primary-light-text);
          border-radius: var(--radius-sm);
          background: var(--admin-primary-light-text);
          color: var(--admin-surface);
          font-weight: 600;
        }
        app-care-extension-panel .p-button.p-button-text,
        app-care-extension-panel .p-button.p-button-outlined {
          background: transparent;
          color: var(--admin-primary-light-text);
        }
        app-care-extension-panel .p-button:disabled {
          opacity: 0.55;
          cursor: not-allowed;
        }
      }
      @media (max-width: 1050px) {
        .extension-grid {
          grid-template-columns: minmax(0, 1fr);
        }
        section {
          padding: 20px;
        }
      }
      @media (max-width: 600px) {
        .extension-table { overflow: visible; }
        thead { display: none; }
        table, tbody, tr { display: block; }
        tr { padding-block: 12px; border-bottom: 1px solid var(--admin-border-light); }
        td { display: block; padding: 8px 0; border: 0; overflow-wrap: anywhere; }
        td[data-label] { display: grid; grid-template-columns: minmax(0, 0.8fr) minmax(0, 1fr); gap: 12px; }
        td[data-label]::before { content: attr(data-label); font-weight: 600; }
      }
    `,
  ],
})
export class CareExtensionPanelComponent implements OnInit {
  http = inject(HttpClient);
  store = inject(CareConnectStore);
  data = signal<CareExtensionOverview | false>(false);
  shared = signal<SharedCareProfile | false>(false);
  loading = signal(true);
  busy = signal(false);
  error = signal(false);
  notice = signal(false);
  profileId = '';
  facilityId = 'an-nhien';
  alertNote = '';
  consent = false;
  fields = ['supportNeeds', 'contact', 'dailyRoutine'];
  selectedFields = ['supportNeeds'];
  async ngOnInit() {
    await this.refresh();
  }
  async refresh() {
    this.loading.set(true);
    try {
      const data = await firstValueFrom(
        this.http.get<CareExtensionOverview>(apiUrl('/api/care/extensions'), HTTP_OPTS),
      );
      this.data.set(data);
      if (!this.profileId)
        this.profileId = data.profiles.find((p) => p.id === 'an')?.id || data.profiles[0]?.id || '';
      this.error.set(false);
    } catch {
      this.error.set(true);
    } finally {
      this.loading.set(false);
    }
  }
  async run(path: string, body: object) {
    this.busy.set(true);
    this.notice.set(false);
    try {
      await firstValueFrom(this.http.post(apiUrl(path), body, HTTP_OPTS));
      this.notice.set(true);
      await this.refresh();
      return true;
    } catch {
      this.error.set(true);
      return false;
    } finally {
      this.busy.set(false);
    }
  }
  async sendAlert(source: 'manual' | 'simulator') {
    if (
      await this.run('/api/care/trial-alerts', {
        profileId: this.profileId,
        clientEventId: crypto.randomUUID(),
        source,
        note: this.alertNote,
      })
    )
      this.alertNote = '';
  }
  async actAlert(id: string, action: string) {
    await this.run(`/api/care/trial-alerts/${id}/${action}`, {});
  }
  toggleField(field: string) {
    this.selectedFields = this.selectedFields.includes(field)
      ? this.selectedFields.filter((f) => f !== field)
      : [...this.selectedFields, field];
    this.consent = false;
  }
  async share() {
    if (
      await this.run('/api/care/profile-grants', {
        profileId: this.profileId,
        facilityId: this.facilityId,
        fields: this.selectedFields,
        consent: this.consent,
        days: 7,
      })
    )
      this.consent = false;
  }
  async revoke(id: string) {
    await this.run(`/api/care/profile-grants/${id}/revoke`, {});
  }
  async readShared(id: string) {
    try {
      this.shared.set(
        await firstValueFrom(
          this.http.get<SharedCareProfile>(
            apiUrl(`/api/care/profile-grants/${id}/shared-profile`),
            HTTP_OPTS,
          ),
        ),
      );
    } catch {
      this.shared.set(false);
      this.error.set(true);
    }
  }
  sharedEntries(p: SharedCareProfile) {
    return Object.entries(p.fields).map(([key, value]) => ({ key, value }));
  }
  profileName(id: string) {
    const data = this.data();
    return data ? data.profiles.find((p) => p.id === id)?.name || id : id;
  }
  facilityName(id: string) {
    return this.store.facilities().find((f) => f.id === id)?.customName || id;
  }
  facilityOptions() {
    return this.store
      .facilities()
      .filter((f) => f.published)
      .map((f) => ({ value: f.id, label: f.customName || f.id }));
  }
  date(value: string) {
    return value
      ? new Intl.DateTimeFormat('vi-VN', {
          dateStyle: 'short',
          timeStyle: 'short',
          timeZone: 'Asia/Ho_Chi_Minh',
        }).format(new Date(value))
      : '';
  }
}
