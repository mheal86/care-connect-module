import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  EventEmitter,
  Input,
  OnChanges,
  OnDestroy,
  OnInit,
  Output,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import * as L from 'leaflet';
import { TranslationService } from '../../../core/services/translation.service';
import { TranslatePipe } from '../../../shared/pipes/translate.pipe';
import { CareFacility } from '../care-connect.model';

@Component({
  selector: 'app-care-facility-map',
  standalone: true,
  imports: [RouterLink, TranslatePipe],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <section class="care-map-panel" [attr.aria-label]="'CARE.MAP.TITLE' | translate">
      <header>
        <div>
          <h3>{{ 'CARE.MAP.TITLE' | translate }}</h3>
          <p>{{ 'CARE.MAP.SUBTITLE' | translate }}</p>
        </div>
        <span>OpenStreetMap</span>
      </header>
      <div
        #mapCanvas
        class="care-map-canvas"
        [attr.aria-label]="'CARE.MAP.CANVAS_LABEL' | translate"
      ></div>
      @if (tileError()) {
        <p role="status">{{ 'CARE.MAP.TILE_ERROR' | translate }}</p>
      }
      <div class="care-map-choices">
        @for (item of locatedFacilities(); track item.id) {
          <button type="button" [class.selected]="isSelected(item)" (click)="selectPin(item)">
            <i class="pi pi-map-marker" aria-hidden="true"></i>{{ facilityName(item) }}
          </button>
        }
      </div>
      @if (selectedFacility(); as active) {
        <article class="care-map-card" aria-live="polite">
          <div>
            <strong>{{ facilityName(active) }}</strong>
            <p>{{ address(active) }}</p>
          </div>
          <a [routerLink]="[basePath + '/facilities', active.id]"
            >{{ 'CARE.VIEW_DETAIL' | translate }}
            <i class="pi pi-arrow-right" aria-hidden="true"></i
          ></a>
        </article>
      }
      <small>{{ 'CARE.MAP.SAMPLE_COORDINATES' | translate }}</small>
    </section>
  `,
  styles: [
    `
      .care-map-panel {
        padding: 24px;
        margin-bottom: 24px;
        background: var(--admin-surface);
        border: 1px solid var(--admin-border-light);
        border-radius: var(--radius-lg);
      }
      header {
        display: flex;
        justify-content: space-between;
        gap: 20px;
        margin-bottom: 18px;
      }
      h3,
      p {
        margin: 0 0 8px;
      }
      header p,
      small {
        color: var(--admin-text-muted);
      }
      header span {
        color: var(--admin-primary-light-text);
      }
      .care-map-canvas {
        height: 340px;
        border-radius: var(--radius-md);
        overflow: hidden;
        z-index: 0;
      }
      .care-map-choices {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin: 16px 0;
      }
      button {
        min-height: 44px;
        padding: 10px 14px;
        border: 1px solid var(--admin-border-light);
        border-radius: var(--radius-sm);
        background: var(--admin-surface);
        color: var(--admin-text-primary);
        cursor: pointer;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      button.selected {
        background: var(--admin-primary-light);
        color: var(--admin-primary-light-text);
        border-color: var(--admin-primary-light-text);
      }
      .care-map-card {
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 12px;
      }
      a {
        color: var(--admin-primary-light-text);
      }
      :focus-visible {
        outline: 3px solid var(--admin-primary-light-text);
        outline-offset: 3px;
      }
      ::ng-deep .care-map-canvas .leaflet-control-attribution {
        font-size: 11px;
      }
      @media (max-width: 600px) {
        .care-map-panel {
          padding: 16px;
        }
        .care-map-canvas {
          height: 300px;
        }
      }
    `,
  ],
})
export class CareFacilityMapComponent implements OnInit, AfterViewInit, OnChanges, OnDestroy {
  @Input() facilities: CareFacility[] = [];
  @Input() basePath = '/care-connect';
  @Output() facilityPick = new EventEmitter<CareFacility>();
  @ViewChild('mapCanvas') canvas!: ElementRef<HTMLDivElement>;
  i18n = inject(TranslationService);
  selectedFacility = signal<CareFacility | false>(false);
  tileError = signal(false);
  mapInstance: L.Map | false = false;
  markers: L.LayerGroup | false = false;
  ngOnInit() {}
  ngAfterViewInit() {
    this.mapInstance = L.map(this.canvas.nativeElement, { scrollWheelZoom: false }).setView(
      [10.77, 106.7],
      11,
    );
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    })
      .on('tileerror', () => this.tileError.set(true))
      .addTo(this.mapInstance);
    this.markers = L.layerGroup().addTo(this.mapInstance);
    this.renderMarkers();
  }
  ngOnChanges() {
    this.renderMarkers();
  }
  isSelected(f: CareFacility) {
    const selected = this.selectedFacility();
    return selected !== false && selected.id === f.id;
  }
  renderMarkers() {
    if (!this.mapInstance || !this.markers) return;
    this.markers.clearLayers();
    const points: L.LatLngTuple[] = [];
    const color = getComputedStyle(this.canvas.nativeElement)
      .getPropertyValue('--admin-primary-light-text')
      .trim();
    for (const item of this.locatedFacilities()) {
      const latlng: L.LatLngTuple = [item.lat || 0, item.lng || 0];
      points.push(latlng);
      L.circleMarker(latlng, { radius: 10, color, fillColor: color, fillOpacity: 0.8, weight: 3 })
        .bindTooltip(this.facilityName(item), { permanent: false })
        .on('click', () => this.selectPin(item))
        .addTo(this.markers);
    }
    if (points.length) {
      this.mapInstance.fitBounds(L.latLngBounds(points), { padding: [30, 30], maxZoom: 13 });
      if (!this.selectedFacility()) this.selectedFacility.set(this.locatedFacilities()[0]);
    }
  }
  locatedFacilities() {
    return this.facilities.filter(
      (f) => f.published && Number.isFinite(f.lat) && Number.isFinite(f.lng),
    );
  }
  facilityName(f: CareFacility) {
    return f.customName || this.i18n.translate(`CARE.DATA.${f.key}`);
  }
  address(f: CareFacility) {
    return f.customAddress || this.i18n.translate(`CARE.ADDRESS.${f.addressKey}`);
  }
  selectPin(f: CareFacility) {
    this.selectedFacility.set(f);
    this.facilityPick.emit(f);
    if (this.mapInstance) this.mapInstance.panTo([f.lat || 0, f.lng || 0]);
  }
  ngOnDestroy() {
    if (this.mapInstance) this.mapInstance.remove();
  }
}
