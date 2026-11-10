import { ChangeDetectionStrategy, Component, OnDestroy, ViewEncapsulation, computed, inject } from "@angular/core";
import { FormControl, FormGroup, ReactiveFormsModule, Validators } from "@angular/forms";
import { MatButtonModule } from "@angular/material/button";
import { MatFormFieldModule } from "@angular/material/form-field";
import { MatInputModule } from "@angular/material/input";
import { Router } from "@angular/router";
import { StatusService } from "@shared/services/status.service";
import { SetupPageService } from "./setup.service";

@Component({
	selector: "penniless-setup",
	imports: [ReactiveFormsModule, MatButtonModule, MatFormFieldModule, MatInputModule],
	templateUrl: "./setup.page.html",
	styleUrl: "./setup.page.scss",
	changeDetection: ChangeDetectionStrategy.OnPush,
	encapsulation: ViewEncapsulation.None,
})
export class SetupPage implements OnDestroy {
	private readonly router = inject(Router);
	private readonly statusService = inject(StatusService);

	protected readonly service = inject(SetupPageService);

	protected readonly setupForm = new FormGroup({
		setupToken: new FormControl("", { nonNullable: true, validators: [Validators.required] }),
	});

	protected readonly isFixtureMode = computed(() => this.statusService.status()?.source === "fixture");

	ngOnDestroy(): void {
		this.service.reset();
	}

	protected submit(): void {
		if (this.setupForm.invalid) {
			this.setupForm.markAllAsTouched();

			return;
		}

		this.service.connect(this.setupForm.getRawValue().setupToken.trim(), () => {
			this.router.navigate(["/dashboard"], { replaceUrl: true });
		});
	}
}
