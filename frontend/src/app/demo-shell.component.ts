import { Component, OnInit, inject, signal } from '@angular/core';
import { Router, RouterOutlet } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

@Component({
  selector: 'app-root', standalone: true, imports: [RouterOutlet, FormsModule],
  template: `@if (checking()) {
    <main class="demo-login"><p role="status">Đang kiểm tra phiên đăng nhập…</p></main>
  } @else if (ready()) {
    <header class="demo-bar" aria-label="Phiên chạy thử">
      <strong>Care Connect</strong>
      <div class="demo-account"><span>{{ username }}</span><button type="button" (click)="logout()">Đổi tài khoản</button></div>
    </header>
    <router-outlet />
  } @else {
    <main class="demo-login">
      <h1>Care Connect</h1>
      <p>Đăng nhập để chạy thử module kết nối cơ sở chăm sóc bằng dữ liệu minh họa.</p>
      <form (ngSubmit)="login()">
        <label for="demo-user">Tài khoản</label>
        <select id="demo-user" name="username" [(ngModel)]="username">
          <option value="family_demo">Gia đình mẫu</option>
          <option value="staff_demo">Nhân viên và quản lý cơ sở</option>
          <option value="elder_demo">Người cao tuổi mẫu</option>
          <option value="other_demo">Gia đình khác</option>
        </select>
        <label for="demo-password">Mật khẩu demo</label>
        <input id="demo-password" name="password" type="password" [(ngModel)]="password" aria-describedby="demo-password-help" autocomplete="current-password" required />
        <p id="demo-password-help" class="demo-help">Nhập giá trị sau dấu = của DEMO_PASSWORD trong tệp .env tại máy, không nhập chữ DEMO_PASSWORD.</p>
        <button type="submit" [disabled]="busy()">{{ busy() ? 'Đang đăng nhập…' : 'Mở module' }}</button>
      </form>
      @if (error()) { <p class="demo-error" role="alert">{{ error() }}</p> }
    </main>
  }`,
})
export class DemoShellComponent implements OnInit {
  http = inject(HttpClient);
  router = inject(Router);
  checking = signal(true);
  ready = signal(false);
  busy = signal(false);
  error = signal('');
  username = 'family_demo';
  password = '';

  async ngOnInit() {
    try {
      const result = await firstValueFrom(this.http.get<{username:string}>('/api/demo/me', {withCredentials:true}));
      this.username = result.username;
      this.ready.set(true);
    } catch {
      this.ready.set(false);
    } finally {
      this.checking.set(false);
    }
  }

  async login() {
    if (this.busy()) return;
    this.busy.set(true);
    this.error.set('');
    try {
      await firstValueFrom(this.http.post('/api/demo/login', {username:this.username,password:this.password}, {withCredentials:true}));
      this.password = '';
      this.ready.set(true);
      await this.router.navigateByUrl('/care-connect');
    } catch (error) {
      this.error.set(error instanceof HttpErrorResponse && error.status === 401
        ? 'Tài khoản hoặc mật khẩu chưa đúng. Hãy nhập giá trị DEMO_PASSWORD trong tệp .env tại máy.'
        : 'Chưa kết nối được máy chủ. Kiểm tra backend ở cổng 8008 rồi thử lại.');
    } finally {
      this.busy.set(false);
    }
  }

  async logout() {
    try {
      await firstValueFrom(this.http.post('/api/demo/logout', {}, {withCredentials:true}));
      window.location.assign('/care-connect');
    } catch {
      this.error.set('Chưa đổi được tài khoản. Kiểm tra kết nối rồi thử lại.');
    }
  }
}
