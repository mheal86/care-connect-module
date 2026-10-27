import { Routes } from '@angular/router';
import {
  CARE_CONNECT_API,
  CareConnectHttpApi,
} from '../../core/api/care-connect.service';
import { CareConnectStore } from './care-connect.store';

const page = () => import('./care-connect.page').then((module) => module.CareConnectPage);

export const CARE_CONNECT_ROUTES: Routes = [
  {
    path: '',
    providers: [{ provide: CARE_CONNECT_API, useExisting: CareConnectHttpApi }, CareConnectStore],
    children: [
      { path: '', pathMatch: 'full', loadComponent: page, data: { view: 'facilities' } },
      { path: 'facilities/:id', loadComponent: page, data: { view: 'facility' } },
      { path: 'facilities/:id/consult', loadComponent: page, data: { view: 'consult' } },
      { path: 'requests', loadComponent: page, data: { view: 'requests' } },
      { path: 'requests/:id', loadComponent: page, data: { view: 'request' } },
      { path: 'inbox', loadComponent: page, data: { view: 'inbox' } },
      { path: 'inbox/:id', loadComponent: page, data: { view: 'request', staff: true } },
      { path: 'extensions', loadComponent: page, data: { view: 'extensions' } },
      { path: 'catalog', loadComponent: page, data: { view: 'catalog' } },
    ],
  },
];

// Reuse the same workflow and route-scoped store; /care-connect-v2 stays on fixture data for report demos.
export const CARE_CONNECT_ALTERNATIVE_ROUTES: Routes = CARE_CONNECT_ROUTES.map((route) => ({
  ...route,
  providers: [{ provide: CARE_CONNECT_API, useExisting: CareConnectHttpApi }, CareConnectStore],
  children: route.children?.map((child) => ({
    ...child,
    data: { ...child.data, alternative: true },
  })),
}));
