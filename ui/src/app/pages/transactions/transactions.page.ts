import { ChangeDetectionStrategy, Component, ViewEncapsulation } from "@angular/core";

@Component({
	selector: "penniless-transactions",
	templateUrl: "./transactions.page.html",
	styleUrl: "./transactions.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class TransactionsPage {}
