import { ComponentFixture, TestBed } from '@angular/core/testing';
import { StatusPillComponent } from './status-pill.component';

describe('StatusPillComponent', () => {
  let fixture: ComponentFixture<StatusPillComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [StatusPillComponent] }).compileComponents();
    fixture = TestBed.createComponent(StatusPillComponent);
  });

  it('maps a completed status to the success treatment', () => {
    fixture.componentRef.setInput('status', 'completed');
    fixture.detectChanges();

    expect(fixture.nativeElement.querySelector('.pill').classList).toContain('success');
  });
});
