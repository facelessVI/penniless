import { DatePipe } from "@angular/common";
import { ChangeDetectionStrategy, Component, OnDestroy, OnInit, ViewEncapsulation, inject } from "@angular/core";
import { MatButtonModule } from "@angular/material/button";
import { MatButtonToggleChange, MatButtonToggleModule } from "@angular/material/button-toggle";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { MatSelectChange, MatSelectModule } from "@angular/material/select";
import { MatSlideToggleChange, MatSlideToggleModule } from "@angular/material/slide-toggle";
import { MatTableModule } from "@angular/material/table";
import { ActivatedRoute } from "@angular/router";
import { fromIsoDate } from "@shared/utils/date.util";
import { DatePreset, PAGE_SIZE_OPTIONS, TransactionsPageService } from "./transactions.service";

@Component({
	selector: "penniless-transactions",
	imports: [
		DatePipe,
		MatButtonModule,
		MatButtonToggleModule,
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

	protected readonly service = inject(TransactionsPageService);
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
		this.service.initCategory(this.route.snapshot.queryParamMap.get("category"));
		this.service.loadFilterOptions();
		this.service.getPage();
	}

	ngOnDestroy(): void {
		this.service.reset();
	}

	protected onPresetChange(event: MatButtonToggleChange): void {
		this.service.setPreset(event.value as DatePreset);
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

	protected onCustomStartChange(event: globalThis.Event): void {
		this.service.setCustomStart(fromIsoDate((event.target as HTMLInputElement).value));
	}

	protected onCustomEndChange(event: globalThis.Event): void {
		this.service.setCustomEnd(fromIsoDate((event.target as HTMLInputElement).value));
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
}
