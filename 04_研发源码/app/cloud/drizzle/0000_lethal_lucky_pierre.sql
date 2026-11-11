CREATE TABLE `audits` (
	`id` text PRIMARY KEY NOT NULL,
	`actor` text NOT NULL,
	`action` text NOT NULL,
	`target` text NOT NULL,
	`detail` text NOT NULL,
	`at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `contents` (
	`kind` text NOT NULL,
	`id` text NOT NULL,
	`data` text NOT NULL,
	`status` text NOT NULL,
	`position` integer DEFAULT 0 NOT NULL,
	`updated` integer NOT NULL,
	PRIMARY KEY(`kind`, `id`)
);
--> statement-breakpoint
CREATE TABLE `devices` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`provider` text NOT NULL,
	`device_id` text NOT NULL,
	`map` text NOT NULL,
	`status` text NOT NULL,
	`consent_at` integer NOT NULL,
	FOREIGN KEY (`owner`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE UNIQUE INDEX `devices_unique` ON `devices` (`owner`,`provider`,`device_id`,`map`);--> statement-breakpoint
CREATE TABLE `friendships` (
	`sender` text,
	`recipient` text,
	`status` text NOT NULL,
	`created` integer NOT NULL,
	PRIMARY KEY(`sender`, `recipient`),
	FOREIGN KEY (`sender`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`recipient`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `measurements` (
	`id` text PRIMARY KEY NOT NULL,
	`connection_id` text,
	`metric` text NOT NULL,
	`value` real NOT NULL,
	`unit` text NOT NULL,
	`measured_at` text NOT NULL,
	FOREIGN KEY (`connection_id`) REFERENCES `devices`(`id`) ON UPDATE no action ON DELETE cascade
);
--> statement-breakpoint
CREATE UNIQUE INDEX `measurements_unique` ON `measurements` (`connection_id`,`metric`,`measured_at`);--> statement-breakpoint
CREATE TABLE `media` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`mime` text NOT NULL,
	`filename` text NOT NULL,
	`object_key` text NOT NULL,
	`created` integer NOT NULL,
	FOREIGN KEY (`owner`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `messages` (
	`id` text PRIMARY KEY NOT NULL,
	`sender` text,
	`recipient` text,
	`body` text NOT NULL,
	`created` integer NOT NULL,
	FOREIGN KEY (`sender`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action,
	FOREIGN KEY (`recipient`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `posts` (
	`id` text PRIMARY KEY NOT NULL,
	`author_id` text NOT NULL,
	`title` text NOT NULL,
	`body` text NOT NULL,
	`media_url` text DEFAULT '' NOT NULL,
	`status` text NOT NULL,
	`reason` text DEFAULT '' NOT NULL,
	`created` integer NOT NULL,
	`updated` integer NOT NULL,
	FOREIGN KEY (`author_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `rate_limits` (
	`key` text PRIMARY KEY NOT NULL,
	`count` integer NOT NULL,
	`expires` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `records` (
	`owner` text NOT NULL,
	`kind` text NOT NULL,
	`day` text NOT NULL,
	`data` text NOT NULL,
	`created` integer NOT NULL,
	PRIMARY KEY(`owner`, `kind`, `day`)
);
--> statement-breakpoint
CREATE TABLE `revisions` (
	`id` text PRIMARY KEY NOT NULL,
	`actor` text NOT NULL,
	`kind` text NOT NULL,
	`item_id` text NOT NULL,
	`snapshot` text NOT NULL,
	`at` integer NOT NULL
);
--> statement-breakpoint
CREATE TABLE `service_requests` (
	`id` text PRIMARY KEY NOT NULL,
	`user_id` text,
	`teacher_id` text NOT NULL,
	`teacher_name` text NOT NULL,
	`body` text NOT NULL,
	`preferred_date` text NOT NULL,
	`status` text NOT NULL,
	`created` integer NOT NULL,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `sessions` (
	`token` text PRIMARY KEY NOT NULL,
	`user_id` text,
	`expires` integer NOT NULL,
	FOREIGN KEY (`user_id`) REFERENCES `users`(`id`) ON UPDATE no action ON DELETE no action
);
--> statement-breakpoint
CREATE TABLE `settings` (
	`key` text PRIMARY KEY NOT NULL,
	`data` text NOT NULL
);
--> statement-breakpoint
CREATE TABLE `timer_runs` (
	`id` text PRIMARY KEY NOT NULL,
	`owner` text NOT NULL,
	`start_ms` integer NOT NULL,
	`end_ms` integer,
	`last_seen` integer NOT NULL,
	`zone` text NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `one_open_timer` ON `timer_runs` (`owner`) WHERE "timer_runs"."end_ms" IS NULL;--> statement-breakpoint
CREATE TABLE `users` (
	`id` text PRIMARY KEY NOT NULL,
	`username` text NOT NULL,
	`password` text NOT NULL,
	`name` text NOT NULL,
	`role` text NOT NULL,
	`created` integer NOT NULL
);
--> statement-breakpoint
CREATE UNIQUE INDEX `users_username_unique` ON `users` (`username`);--> statement-breakpoint
CREATE UNIQUE INDEX `one_bootstrap_admin` ON `users` (`username`);