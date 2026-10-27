import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';
interface TranslationTree { [key: string]: string | TranslationTree; }
@Injectable({ providedIn: 'root' })
export class TranslationService {
  http = inject(HttpClient);
  translations = signal<TranslationTree>({});
  currentLang = signal('vi');
  async loadTranslations(lang: string) {
    this.translations.set(await firstValueFrom(this.http.get<TranslationTree>(`/assets/i18n/${lang}.json`)));
    this.currentLang.set(lang);
  }
  translate(key: string): string {
    let value: string | TranslationTree = this.translations();
    for (const part of key.split('.')) {
      if (typeof value === 'string' || !(part in value)) return key;
      value = value[part];
    }
    return typeof value === 'string' ? value : key;
  }
}
