import { inject, provideAppInitializer } from '@angular/core';
import { bootstrapApplication } from '@angular/platform-browser';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { DemoShellComponent } from './app/demo-shell.component';
import { CARE_CONNECT_ROUTES, CARE_CONNECT_ALTERNATIVE_ROUTES } from './app/features/care-connect/care-connect.routes';
import { TranslationService } from './app/core/services/translation.service';

bootstrapApplication(DemoShellComponent, {providers:[provideHttpClient(), provideRouter([
  {path:'care-connect', children:CARE_CONNECT_ROUTES},
  {path:'care-connect-v2', children:CARE_CONNECT_ALTERNATIVE_ROUTES},
  {path:'**', redirectTo:'care-connect'},
]), provideAppInitializer(() => inject(TranslationService).loadTranslations('vi'))]}).catch(error => console.error(error));
