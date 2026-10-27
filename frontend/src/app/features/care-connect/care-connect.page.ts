import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormBuilder, FormsModule, ReactiveFormsModule, Validators } from '@angular/forms';
import { combineLatest } from 'rxjs';
import { ButtonModule } from 'primeng/button';
import { DialogModule } from 'primeng/dialog';
import { InputTextModule } from 'primeng/inputtext';
import { SelectModule } from 'primeng/select';
import { SkeletonModule } from 'primeng/skeleton';
import { TranslationService } from '../../core/services/translation.service';
import { TranslatePipe } from '../../shared/pipes/translate.pipe';
import { BRAND_ICON_SRC } from '../../constant/dashboard.constants';
import { CareConnectStore } from './care-connect.store';
import { CareExtensionPanelComponent } from './components/care-extension-panel.component';
import { CareFacilityMapComponent } from './components/care-facility-map.component';
import {
  CARE_FEEDBACK_TAGS,
  CARE_PRIORITY_TAGS,
  CARE_SERVICES,
  CARE_STATUSES,
  CARE_SUPPORT_LEVELS,
  STAFF_FACILITY_ID,
  CareAction,
  CareConsultSlot,
  CareFacility,
  CareFilters,
  CareRecommendationCriteria,
  CareRequest,
  CareService,
  CareServiceId,
  CareStatus,
  CareView,
  careAllowedActions,
  careLocalDate,
  careSearchText,
  careUtc,
} from './care-connect.model';

function toVietnamLocalInput(utcIso: string): string {
  const ms = Date.parse(utcIso);
  if (!Number.isFinite(ms)) return careLocalDate(3, 9);
  return new Date(ms + 7 * 60 * 60 * 1000).toISOString().slice(0, 16);
}

@Component({
  selector: 'app-care-connect',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    ReactiveFormsModule,
    ButtonModule,
    DialogModule,
    InputTextModule,
    SelectModule,
    SkeletonModule,
    TranslatePipe,
    CareFacilityMapComponent,
    CareExtensionPanelComponent,
  ],
  templateUrl: './care-connect.page.html',
  styleUrls: ['./care-connect.page.scss', './care-connect-alternative.scss'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CareConnectPage implements OnInit {
  store = inject(CareConnectStore);
  i18n = inject(TranslationService);
  router = inject(Router);
  route = inject(ActivatedRoute);
  destroyRef = inject(DestroyRef);
  element = inject<ElementRef<HTMLElement>>(ElementRef);
  fb = inject(FormBuilder);
  brandIcon = BRAND_ICON_SRC;
  alternative = this.route.snapshot.data['alternative'] === true;
  basePath = this.alternative ? '/care-connect-v2' : '/care-connect';
  view = this.route.snapshot.data['view'] as CareView;
  staff = this.route.snapshot.data['staff'] === true;
  id = signal('');
  state = signal('ready');
  page = signal(1);
  status = signal('');
  requestQuery = signal('');
  filters = signal<CareFilters>({ q: '', region: '', type: '', service: '' });
  draftFilters: CareFilters = { q: '', region: '', type: '', service: '' };
  review = signal(false);
  attempted = signal(false);
  sending = signal(false);
  feedback = signal('');
  formError = signal('');
  requestKey = crypto.randomUUID();
  minimumDate = careLocalDate(0, 0);
  actionOpen = false;
  currentAction: CareAction = 'CANCEL';
  actionVersion = 0;
  actionMessage = '';
  actionTime = careLocalDate(4, 14);
  actionError = '';
  catalogOpen = false;
  catalogNew = false;
  catalogError = '';
  editingFacility: CareFacility = {
    id: '',
    key: '',
    region: 'hcm',
    type: 'residential',
    addressKey: '',
    descriptionKey: '',
    services: [],
    published: false,
    updatedAt: '',
    amenities: [],
  };

  // P4 Extension: Map, Explainable Recommendations, Comparison, Capacity Slots & Moderated Feedback
  showMap = signal(false);
  recommendOpen = false;
  compareOpen = false;
  recCriteria: CareRecommendationCriteria = {
    region: 'hcm',
    serviceId: 'longstay',
    supportLevel: 'L2',
    budgetMaxVnd: 15000000,
    priorityTags: ['nursing', 'garden'],
  };
  supportLevels = CARE_SUPPORT_LEVELS;
  priorityTagOptions = CARE_PRIORITY_TAGS;
  feedbackTagOptions = CARE_FEEDBACK_TAGS;
  compareServiceIds = CARE_SERVICES;
  selectedSlotId = signal('');
  reminderOptIn = signal(false);
  feedbackRating = signal(5);
  feedbackTags = signal<string[]>(['DEDICATED', 'CLEAR_INFO']);
  feedbackComment = signal('');

  navItems = [
    {
      path: this.basePath,
      key: 'FIND',
      icon: 'pi pi-building',
      views: ['facilities', 'facility', 'consult'],
    },
    {
      path: this.basePath + '/requests',
      key: 'MY_REQUESTS',
      icon: 'pi pi-file',
      views: ['requests', 'request'],
    },
    { path: this.basePath + '/inbox', key: 'INBOX', icon: 'pi pi-inbox', views: ['inbox'] },
    {
      path: this.basePath + '/extensions',
      key: 'EXTENSIONS',
      icon: 'pi pi-share-alt',
      views: ['extensions'],
    },
    {
      path: this.basePath + '/catalog',
      key: 'CATALOG',
      icon: 'pi pi-sliders-h',
      views: ['catalog'],
    },
  ];
  form = this.fb.nonNullable.group({
    profile: ['an', Validators.required],
    service: ['', Validators.required],
    needs: ['', [Validators.required, Validators.minLength(20), Validators.maxLength(1000)]],
    time: [careLocalDate(3, 9), Validators.required],
    contactName: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(100)]],
    phone: ['', [Validators.required, Validators.pattern(/^(0\d{9}|\+84\d{9})$/)]],
    note: ['', Validators.maxLength(1000)],
    consent: [false, Validators.requiredTrue],
  });
  facility = computed(() => this.store.facilities().find((item) => item.id === this.id()));
  facilitySlots = computed(() => this.store.slotsForFacility(this.id()));
  facilityFeedback = computed(() =>
    this.store.feedbackForFacility(this.id(), this.staff || this.view === 'catalog'),
  );
  pendingFeedbacks = computed(() =>
    this.store.feedbacks().filter((fb) => fb.moderationStatus === 'pending'),
  );
  request = computed(() =>
    this.store
      .requests()
      .find(
        (item) =>
          item.id === this.id() &&
          (!this.staff ||
            (this.store.fixture
              ? item.facilityId === STAFF_FACILITY_ID
              : this.store.memberIds().includes(item.facilityId))),
      ),
  );
  matchingFacilities = computed(() => {
    const filters = this.filters();
    return this.store
      .facilities()
      .filter(
        (item) =>
          item.published &&
          (!filters.q ||
            careSearchText(`${this.facilityName(item)} ${this.address(item)}`).includes(
              careSearchText(filters.q),
            )) &&
          (!filters.region || item.region === filters.region) &&
          (!filters.type || item.type === filters.type) &&
          (!filters.service ||
            item.services.some((service) => service.id === filters.service && service.accepting)),
      );
  });
  visibleFacilities = computed(() =>
    this.state() === 'empty'
      ? []
      : this.matchingFacilities().slice((this.page() - 1) * 4, this.page() * 4),
  );
  matchingRequests = computed(() =>
    this.store
      .requests()
      .filter(
        (item) =>
          (this.view !== 'inbox' ||
            (this.store.fixture
              ? item.facilityId === STAFF_FACILITY_ID
              : this.store.memberIds().includes(item.facilityId))) &&
          (!this.status() || item.status === this.status()) &&
          (!this.requestQuery() ||
            careSearchText(`${item.id} ${this.facilityNameById(item.facilityId)}`).includes(
              careSearchText(this.requestQuery()),
            )),
      )
      .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt) || b.id.localeCompare(a.id)),
  );
  visibleRequests = computed(() =>
    this.state() === 'empty'
      ? []
      : this.matchingRequests().slice((this.page() - 1) * 6, this.page() * 6),
  );

  private syncConsultService() {
    if (this.view !== 'consult' || !this.facility()) return;
    const requestedService = this.route.snapshot.queryParamMap.get('service');
    const selected = this.facility()?.services.find(
      (item) => item.id === requestedService && item.accepting,
    );
    this.form.controls.service.setValue(
      requestedService
        ? selected?.id || ''
        : this.facility()?.services.find((item) => item.accepting)?.id || '',
    );
    if (requestedService && !selected) this.formError.set('UNAVAILABLE');
  }

  async ngOnInit() {
    combineLatest([this.route.paramMap, this.route.queryParamMap])
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ([params, query]) => {
          this.id.set(params.get('id') || '');
          const requestedPage = Number(query.get('page'));
          this.page.set(
            Number.isFinite(requestedPage) ? Math.max(1, Math.floor(requestedPage)) : 1,
          );
          this.status.set(
            CARE_STATUSES.includes(query.get('status') as CareStatus)
              ? query.get('status') || ''
              : '',
          );
          this.requestQuery.set(query.get('q') || '');
          this.filters.set({
            q: query.get('q') || '',
            region: query.get('region') || '',
            type: query.get('type') || '',
            service:
              this.view === 'consult'
                ? query.get('filterService') || ''
                : query.get('service') || '',
          });
          this.draftFilters = { ...this.filters() };
          const compareParam = query.get('compare');
          if (compareParam) {
            this.store.setCompareIds(compareParam.split(',').filter(Boolean));
          }
          this.state.set(
            ['loading', 'empty', 'error', 'conflict'].includes(query.get('state') || '')
              ? query.get('state') || 'ready'
              : 'ready',
          );
          this.syncConsultService();
          const maximum = this.totalPages();
          if (this.page() > maximum) this.page.set(maximum);
        },
        error: () => this.state.set('error'),
        complete: () => {},
      });
    await this.store.load(this.staff || this.view === 'inbox' ? 'inbox' : 'mine');
    if (
      !this.store.fixture &&
      !this.store.profiles().some((p) => p.id === this.form.controls.profile.value)
    )
      this.form.controls.profile.setValue(this.store.profiles()[0]?.id || '');
    this.syncConsultService();
    const maximum = this.totalPages();
    if (this.page() > maximum) this.page.set(maximum);
  }

  text(key: string) {
    return this.i18n.translate(`CARE.${key}`);
  }
  options(group: string, values: string[], all = true) {
    return [
      ...(all ? [{ label: this.text(`ALL_${group}`), value: '' }] : []),
      ...values.map((value) => ({ label: this.text(`${group}.${value}`), value })),
    ];
  }
  regionOptions() {
    return this.options('REGION', ['hcm', 'hanoi', 'danang']);
  }
  typeOptions() {
    return this.options('TYPE', ['residential', 'health', 'daycare']);
  }
  serviceOptions() {
    return this.options('SERVICE', CARE_SERVICES);
  }
  supportLevelOptions() {
    return this.supportLevels.map((lvl) => ({
      label: this.text(`RECOMMEND.SUPPORT_${lvl}`),
      value: lvl,
    }));
  }
  statusOptions() {
    return [
      { label: this.text('ALL_STATUS'), value: '' },
      ...CARE_STATUSES.map((value) => ({
        label: this.i18n.translate(this.statusKey(value)),
        value,
      })),
    ];
  }
  // Staff screens describe the same status from the facility side.
  statusKey(status: CareStatus) {
    return (this.staff || this.view === 'inbox') && status === 'SCHEDULE_PROPOSED'
      ? 'CARE.STATUS_STAFF.SCHEDULE_PROPOSED'
      : `CARE.STATUS.${status}`;
  }
  statusHelpKey(status: CareStatus) {
    return `CARE.${this.staff ? 'STATUS_HELP_STAFF' : 'STATUS_HELP'}.${status}`;
  }
  profileOptions() {
    if (!this.store.fixture)
      return this.store.profiles().map((p) => ({ value: p.id, label: p.name }));
    return this.options('PROFILE', ['an', 'mai'], false);
  }
  profileName(id: string) {
    const name = this.store.profiles().find((p) => p.id === id)?.name;
    if (name) return name;
    const translated = this.text(`PROFILE.${id}`);
    return translated.startsWith('CARE.') ? this.text('PROFILE_FALLBACK') : translated;
  }
  availableServices() {
    return this.options(
      'SERVICE',
      this.facility()
        ?.services.filter((item) => item.accepting)
        .map((item) => item.id) || [],
      false,
    );
  }
  stateOptions() {
    return this.options(
      'STATE',
      this.view === 'request' ? ['ready', 'conflict'] : ['ready', 'loading', 'empty', 'error'],
      false,
    );
  }
  facilityName(item: CareFacility) {
    return item.customName || this.text(`DATA.${item.key}`);
  }
  isReceiving(item: CareFacility) {
    return item.services.some((service) => service.accepting);
  }
  referenceService(item: CareFacility): CareService {
    return (
      item.services.find((service) => service.id === this.filters().service && service.accepting) ||
      item.services.find((service) => service.accepting) ||
      item.services[0]
    );
  }
  editDetails() {
    this.form.controls.consent.setValue(false);
    this.review.set(false);
    this.attempted.set(false);
  }
  canAcceptSchedule(item: CareRequest) {
    return (
      Number.isFinite(Date.parse(item.proposedTime)) && Date.parse(item.proposedTime) > Date.now()
    );
  }
  facilityNameById(id: string) {
    const item = this.store.facilities().find((facility) => facility.id === id);
    return item ? this.facilityName(item) : this.store.requests().find(r => r.facilityId === id)?.facilityLabel || this.text('UNPUBLISHED');
  }
  requestFacility(item: CareRequest) {
    return this.store.facilities().find((facility) => facility.id === item.facilityId);
  }
  address(item: CareFacility) {
    return item.customAddress || this.text(`ADDRESS.${item.addressKey}`);
  }
  description(item: CareFacility) {
    return item.customDescription || this.text(`DESCRIPTION.${item.descriptionKey}`);
  }
  price(value: number) {
    return value
      ? new Intl.NumberFormat(this.i18n.currentLang() === 'vi' ? 'vi-VN' : 'en-US', {
          style: 'currency',
          currency: 'VND',
          maximumFractionDigits: 0,
        }).format(value)
      : this.text('NOT_PUBLISHED');
  }
  date(value: string, withTime = true) {
    if (!value) return this.text('NOT_CONFIRMED');
    return new Intl.DateTimeFormat(this.i18n.currentLang() === 'vi' ? 'vi-VN' : 'en-GB', {
      dateStyle: 'medium',
      ...(withTime ? { timeStyle: 'short' as const } : {}),
      timeZone: 'Asia/Ho_Chi_Minh',
    }).format(new Date(value));
  }
  message(value: string) {
    return value.startsWith('CARE.') ? this.i18n.translate(value) : value;
  }
  activeNav(key: string) {
    return this.staff
      ? key === 'INBOX'
      : this.navItems.find((item) => item.key === key)?.views.includes(this.view);
  }
  isStaffOnly() {
    return !this.store.fixture && this.store.memberIds().length > 0 && this.store.profiles().length === 0;
  }
  visibleNavItems() {
    return this.navItems.filter(
      (item) =>
        this.store.fixture ||
        (item.key === 'MY_REQUESTS'
          ? !this.isStaffOnly()
          : item.key === 'INBOX'
            ? this.store.memberIds().length > 0
            : item.key === 'CATALOG'
              ? this.store.managerIds().length > 0
              : true),
    );
  }
  totalPages() {
    return Math.max(
      1,
      Math.ceil(
        ['requests', 'inbox'].includes(this.view)
          ? this.matchingRequests().length / 6
          : this.matchingFacilities().length / 4,
      ),
    );
  }
  applyFilters() {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { ...this.draftFilters, page: 1, state: 'ready' },
      queryParamsHandling: 'merge',
    });
  }
  consultQuery(serviceId: CareServiceId) {
    return { ...this.filters(), filterService: this.filters().service, service: serviceId };
  }
  resetFilters() {
    this.draftFilters = { q: '', region: '', type: '', service: '' };
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { q: '', region: '', type: '', service: '', page: 1, state: 'ready' },
    });
  }
  filterRequests(value: string) {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { status: value, q: this.requestQuery(), page: 1, state: 'ready' },
    });
  }
  changePage(page: number) {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { page },
      queryParamsHandling: 'merge',
    });
    this.element.nativeElement.querySelector<HTMLElement>('h1')?.focus();
  }
  changeState(value: string) {
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { state: value },
      queryParamsHandling: 'merge',
    });
  }
  switchLanguage() {
    this.i18n.loadTranslations(this.i18n.currentLang() === 'vi' ? 'en' : 'vi');
  }
  error(field: keyof typeof this.form.controls) {
    const control = this.form.controls[field];
    return (control.touched || this.attempted()) && control.invalid;
  }

  // P4 methods
  toggleMap() {
    this.showMap.update((v) => !v);
  }
  openRecommend() {
    this.store.recommend(this.recCriteria);
    this.recommendOpen = true;
  }
  runRecommend() {
    this.store.recommend(this.recCriteria);
  }
  togglePriorityTag(tag: string) {
    if (this.recCriteria.priorityTags.includes(tag)) {
      this.recCriteria.priorityTags = this.recCriteria.priorityTags.filter((t) => t !== tag);
    } else {
      this.recCriteria.priorityTags = [...this.recCriteria.priorityTags, tag];
    }
    this.runRecommend();
  }
  toggleCompare(facilityId: string) {
    this.store.toggleCompare(facilityId);
    const ids = this.store.compareIds();
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { compare: ids.length > 0 ? ids.join(',') : '' },
      queryParamsHandling: 'merge',
    });
  }
  isCompared(facilityId: string): boolean {
    return this.store.compareIds().includes(facilityId);
  }
  serviceForFacility(facility: CareFacility, serviceId: CareServiceId): CareService | false {
    return facility.services.find((s) => s.id === serviceId) || false;
  }
  selectSlot(slot: CareConsultSlot) {
    if (slot.bookedCount >= slot.capacity) return;
    this.selectedSlotId.set(slot.id);
    this.form.controls.time.setValue(toVietnamLocalInput(slot.startsAt));
  }
  toggleFeedbackTag(tag: string) {
    const current = this.feedbackTags();
    this.feedbackTags.set(
      current.includes(tag) ? current.filter((t) => t !== tag) : [...current, tag],
    );
  }
  requestHasFeedback(requestId: string): boolean {
    return this.store.feedbacks().some((fb) => fb.requestId === requestId);
  }
  async submitRequestFeedback(requestId: string) {
    const res = await this.store.sendFeedback(
      requestId,
      this.feedbackRating(),
      this.feedbackTags(),
      this.feedbackComment(),
    );
    if (res) {
      this.feedbackComment.set('');
      this.feedback.set('FEEDBACK.SUBMITTED_PENDING');
    }
  }
  async moderateFacilityFeedback(feedbackId: string, status: 'approved' | 'rejected') {
    if (await this.store.reviewFeedback(feedbackId, status)) {
      this.feedback.set('UPDATED');
    }
  }

  nextStep() {
    this.attempted.set(true);
    this.form.patchValue({
      needs: this.form.controls.needs.value.trim(),
      contactName: this.form.controls.contactName.value.trim(),
      phone: this.form.controls.phone.value.replace(/[\s().-]/g, ''),
    });
    const time = this.form.controls.time.value;
    if (!Number.isFinite(Date.parse(careUtc(time))) || Date.parse(careUtc(time)) <= Date.now())
      this.form.controls.time.setErrors({ future: true });
    const fields = ['profile', 'service', 'needs', 'time', 'contactName', 'phone', 'note'] as const;
    if (fields.some((key) => this.form.controls[key].invalid)) {
      this.formError.set('CHECK_FORM');
      setTimeout(() =>
        this.element.nativeElement.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(),
      );
      return;
    }
    this.formError.set('');
    this.attempted.set(false);
    this.form.controls.consent.setValue(false);
    this.review.set(true);
    this.element.nativeElement.querySelector<HTMLElement>('h1')?.focus();
  }
  async submit() {
    this.attempted.set(true);
    if (this.sending() || !this.form.valid) return;
    this.sending.set(true);
    const values = this.form.getRawValue();
    if (
      !Number.isFinite(Date.parse(careUtc(values.time))) ||
      Date.parse(careUtc(values.time)) <= Date.now()
    ) {
      this.formError.set('FUTURE');
      this.sending.set(false);
      return;
    }
    const service = this.facility()?.services.find((item) => item.id === values.service);
    if (!service) {
      this.formError.set('UNAVAILABLE');
      this.sending.set(false);
      return;
    }
    const id = await this.store.submitRequest(
      {
        facilityId: this.id(),
        serviceId: service.id,
        profile: values.profile,
        contactName: values.contactName,
        phone: values.phone,
        needs: values.needs,
        note: values.note,
        preferredTime: careUtc(values.time),
        proposedTime: '',
        confirmedTime: '',
        slotId: this.selectedSlotId() || '',
        reminderOptIn: this.reminderOptIn(),
      },
      this.requestKey,
    );
    if (!id) {
      this.formError.set(this.store.error() || 'UNAVAILABLE');
      this.sending.set(false);
      return;
    }
    await this.router.navigate([this.basePath + '/requests', id], { queryParams: { sent: '1' } });
    this.sending.set(false);
  }
  actions(item: CareRequest) {
    if (!this.store.fixture && this.staff)
      return this.store.memberIds().includes(item.facilityId)
        ? careAllowedActions({ ...item, facilityId: STAFF_FACILITY_ID }, true)
        : [];
    return careAllowedActions(item, this.staff);
  }
  openAction(action: CareAction, item: CareRequest) {
    this.currentAction = action;
    this.actionTime = careLocalDate(4, 14);
    this.actionVersion = item.version;
    this.actionMessage = '';
    this.actionError = '';
    this.actionOpen = true;
  }
  async confirmAction() {
    if (this.store.busy()) return;
    const result = await this.store.applyRequestAction(
      this.id(),
      this.actionVersion,
      this.currentAction,
      this.staff,
      this.actionMessage,
      this.actionTime,
    );
    if (result) {
      this.actionError = result;
      return;
    }
    this.actionOpen = false;
    this.feedback.set('UPDATED');
  }
  selectedTime(item: CareRequest) {
    return item.confirmedTime || item.proposedTime || item.preferredTime;
  }
  hasReason() {
    return ['CANCEL', 'DECLINE', 'PROPOSE_SCHEDULE'].includes(this.currentAction);
  }
  startCatalog(item?: CareFacility) {
    this.catalogNew = !item;
    this.editingFacility = item
      ? structuredClone(item)
      : {
          id: crypto.randomUUID(),
          key: '',
          region: 'hcm',
          type: 'residential',
          addressKey: '',
          descriptionKey: '',
          customName: '',
          customAddress: '',
          customDescription: '',
          contact: '',
          services: [{ id: 'longstay', price: 0, unit: 'month', accepting: true }],
          amenities: [],
          published: false,
          updatedAt: new Date().toISOString(),
        };
    this.editingFacility.customName = item ? this.facilityName(item) : '';
    this.editingFacility.customAddress = item ? this.address(item) : '';
    this.editingFacility.customDescription = item ? this.description(item) : '';
    this.catalogError = '';
    this.catalogOpen = true;
  }
  changeInitialService(id: CareServiceId) {
    this.editingFacility.services = [
      {
        id,
        price: 0,
        unit: id === 'longstay' ? 'month' : id === 'daycare' ? 'day' : 'session',
        accepting: true,
      },
    ];
  }
  addService() {
    const id = CARE_SERVICES.find(
      (service) => !this.editingFacility.services.some((item) => item.id === service),
    );
    if (id)
      this.editingFacility.services.push({
        id,
        price: 0,
        unit: id === 'longstay' ? 'month' : id === 'daycare' ? 'day' : 'session',
        accepting: true,
      });
  }
  async saveCatalog() {
    if (this.store.busy()) return;
    const facility = this.editingFacility;
    const contact = (facility.contact || '').replace(/[\s().-]/g, '');
    if (contact && !/^(0\d{9,10}|\+84\d{9,10})$/.test(contact)) {
      this.catalogError = 'CONTACT_PHONE';
      return;
    }
    if (
      !facility.customName?.trim() ||
      !facility.customAddress?.trim() ||
      !facility.customDescription?.trim() ||
      facility.services.some((service) => !Number.isFinite(service.price) || service.price < 0)
    ) {
      this.catalogError = 'CATALOG_VALIDATION';
      return;
    }
    const saved = await this.store.persistFacility({
      ...facility,
      customName: facility.customName?.trim(),
      customAddress: facility.customAddress?.trim(),
      customDescription: facility.customDescription?.trim(),
      contact,
      updatedAt: new Date().toISOString(),
    });
    if (!saved) {
      this.catalogError = this.store.error() || 'API_ERROR';
      return;
    }
    this.catalogOpen = false;
    this.feedback.set('CATALOG_SAVED');
  }
}
