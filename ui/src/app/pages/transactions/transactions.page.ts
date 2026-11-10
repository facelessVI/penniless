import { ChangeDetectionStrategy, Component, DestroyRef, ElementRef, OnDestroy, OnInit, ViewEncapsulation, inject, viewChild } from "@angular/core";
import { takeUntilDestroyed } from "@angular/core/rxjs-interop";
import { FormControl, FormGroup, ReactiveFormsModule } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatButtonToggleChange, MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatDatepickerModule } from "@angular/material/datepicker";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectChange, MatSelectModule } from "@angular/material/select";
import { MatSlideToggleChange, MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatTableModule } from "@angular/material/table";
import { ActivatedRoute } from "@angular/router";
import { maskTypedDate } from "@shared/utils/date.util";
import { DatePreset, PAGE_SIZE_OPTIONS, TransactionsPageService } from "./transactions.service";

const isSameDay = (first: Date | null, second: Date | null): boolean => first?.getTime() === second?.getTime();

/** A field only counts as entered once its year is whole; a partial year like `202` still parses as a date. */
const COMPLETE_DATE_PATTERN = /^\d{1,2}\/\d{1,2}\/\d{4}$/;

@Component({
	selector: "penniless-transactions",
	imports: [
		ReactiveFormsModule,
		MatButtonModule,
		MatButtonToggleModule,
		MatDatepickerModule,
		MatFormFieldModule,
		MatInputModule,
		MatSelectModule,
		MatSlideToggleModule,
		MatTableModule,
	],
	templateUrl: "./transactions.page.html",
	styleUrl: "./transactions.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class TransactionsPage implements OnInit, OnDestroy {
	private readonly route = inject(ActivatedRoute);
	private readonly destroyRef = inject(DestroyRef);
	private readonly startInput = viewChild<ElementRef<HTMLInputElement>>("startInput");
	private readonly endInput = viewChild<ElementRef<HTMLInputElement>>("endInput");
	private appliedRange: { start: Date | null; end: Date | null } = { start: null, end: null };
	private isDestroyed = false;

	protected readonly service = inject(TransactionsPageService);
	protected readonly rangeForm = new FormGroup({
		start: new FormControl<Date | null>(null),
		end: new FormControl<Date | null>(null),
	});
	protected readonly transactionColumns = ["date", "account", "description", "category", "amount"];
	protected readonly presets: { value: DatePreset; label: string }[] = [
		{ value: "this-month", label: "This month" },
		{ value: "last-month", label: "Last month" },
		{ value: "last-3-months", label: "Last 3 months" },
		{ value: "year-to-date", label: "Year to date" },
		{ value: "custom", label: "Custom" },
	];
	protected readonly pageSizeOptions = PAGE_SIZE_OPTIONS;

	ngOnInit(): void {
		this.setupSubscriptions();
		this.service.initCategory(this.route.snapshot.queryParamMap.get("category"));
		this.service.loadFilterOptions();
		this.service.getPage();
	}

	ngOnDestroy(): void {
		this.isDestroyed = true;
		this.service.reset();
	}

	protected onPresetChange(event: MatButtonToggleChange): void {
		const preset = event.value as DatePreset;

		if (preset === "custom") {
			this.rangeForm.reset({ start: null, end: null });
		}

		this.service.setPreset(preset);
	}

	protected onAccountChange(event: MatSelectChange): void {
		this.service.setAccountId((event.value as string | null) ?? null);
	}

	protected onCategoryChange(event: MatSelectChange): void {
		this.service.setCategory((event.value as string | null) ?? null);
	}

	protected onTransfersChange(event: MatSlideToggleChange): void {
		this.service.setIncludeTransfers(event.checked);
	}

	/** Keeps typed dates in `MM/DD/YYYY` shape; the datepicker itself only parses, it never masks. */
	protected onRangeInput(event: globalThis.Event): void {
		const input = event.target as HTMLInputElement;
		const caret = input.selectionStart ?? input.value.length;
		const masked = maskTypedDate(input.value, caret);

		if (masked.value === input.value) {
			return;
		}

		input.value = masked.value;
		input.setSelectionRange(masked.caret, masked.caret);
		// The datepicker reads the field on `input`; re-dispatch so it parses the masked value. This
		// handler returns early for an already masked value, so the re-dispatch cannot loop.
		input.dispatchEvent(new Event("input"));
	}

	protected onPageSizeChange(event: MatSelectChange): void {
		this.service.setPageSize(Number(event.value));
	}

	protected previousPage(): void {
		this.service.setPageNumber(this.service.pageNumber() - 1);
	}

	protected nextPage(): void {
		this.service.setPageNumber(this.service.pageNumber() + 1);
	}

	private setupSubscriptions(): void {
		this.rangeForm.valueChanges.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
			// The range inputs write their shared selection model after the control emits, so the
			// cross-field validators still see the previous dates until the current task finishes.
			queueMicrotask(() => this.applyCustomRange());
		});
	}

	private applyCustomRange(): void {
		// The microtask below can outlive the page when the user navigates right after typing.
		if (this.isDestroyed) {
			return;
		}

		const start = this.rangeForm.controls.start.value;
		const end = this.rangeForm.controls.end.value;

		if (isSameDay(start, this.appliedRange.start) && isSameDay(end, this.appliedRange.end)) {
			return;
		}

		this.appliedRange = { start, end };

		// Each range input validates the other, so the end field keeps a stale `matEndDateInvalid` after
		// the start is moved in front of it. Re-running both validators is what clears that error; it
		// also re-emits valueChanges, which the guard above stops from looping.
		this.rangeForm.controls.start.updateValueAndValidity();
		this.rangeForm.controls.end.updateValueAndValidity();

		const isReady = this.rangeForm.valid && start !== null && end !== null && this.isDisplayingCompleteDates();

		this.service.setCustomRange(isReady ? start : null, isReady ? end : null);
	}

	private isDisplayingCompleteDates(): boolean {
		const start = this.startInput()?.nativeElement.value ?? "";
		const end = this.endInput()?.nativeElement.value ?? "";

		return COMPLETE_DATE_PATTERN.test(start) && COMPLETE_DATE_PATTERN.test(end);
	}
}
