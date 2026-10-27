import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { provideRouter } from '@angular/router';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { DemoShellComponent } from './demo-shell.component';

describe('Demo sign-in recovery', () => {
  beforeEach(() => TestBed.configureTestingModule({imports:[DemoShellComponent],providers:[provideHttpClient(),provideHttpClientTesting(),provideRouter([])]}));
  afterEach(() => TestBed.inject(HttpTestingController).verify());

  it('explains the configured password after an unauthorized session', async () => {
    const fixture=TestBed.createComponent(DemoShellComponent);
    fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/demo/me').flush({}, {status:401,statusText:'Unauthorized'});
    await fixture.whenStable();fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('#demo-password-help').textContent).toContain('không nhập chữ DEMO_PASSWORD');
    expect(fixture.nativeElement.querySelector('input[type=password]')).toBeTruthy();
  });

  it('distinguishes a bad password from an unavailable backend and permits retry', async () => {
    const fixture=TestBed.createComponent(DemoShellComponent);fixture.detectChanges();
    const http=TestBed.inject(HttpTestingController);
    http.expectOne('/api/demo/me').flush({}, {status:401,statusText:'Unauthorized'});
    await fixture.whenStable();
    fixture.componentInstance.password='wrong-password';
    const first=fixture.componentInstance.login();
    http.expectOne('/api/demo/login').flush({}, {status:401,statusText:'Unauthorized'});
    await first;fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]').textContent).toContain('Tài khoản hoặc mật khẩu');
    expect(fixture.nativeElement.querySelector('button[type=submit]').disabled).toBe(false);
    const second=fixture.componentInstance.login();
    http.expectOne('/api/demo/login').flush({}, {status:502,statusText:'Bad Gateway'});
    await second;fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role=alert]').textContent).toContain('cổng 8008');
  });

  it('restores the signed-in account without leaving the sign-in form visible', async () => {
    const fixture=TestBed.createComponent(DemoShellComponent);fixture.detectChanges();
    TestBed.inject(HttpTestingController).expectOne('/api/demo/me').flush({username:'staff_demo'});
    await fixture.whenStable();fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.demo-bar').textContent).toContain('staff_demo');
    expect(fixture.nativeElement.querySelector('input[type=password]')).toBeNull();
  });
});
