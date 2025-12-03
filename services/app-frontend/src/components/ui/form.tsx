import * as React from "react";
import {
  Controller,
  FormProvider,
  type FieldValues,
  type Path,
  type UseFormReturn,
  type ControllerRenderProps,
  type Control,
  type UseControllerProps,
} from "react-hook-form";

import { cn } from "@/lib/utils";

export type FormProps<TFormValues extends FieldValues> = {
  form?: UseFormReturn<TFormValues>;
  children?: React.ReactNode;
} & React.FormHTMLAttributes<HTMLFormElement>;

export function Form<TFormValues extends FieldValues>({ form, children, className, ...props }: FormProps<TFormValues>) {
  if (!form) {
    // Render a plain HTML form if no react-hook-form is provided
    return (
      <form className={cn("w-full", className)} {...props}>
        {children}
      </form>
    );
  }

  return (
    <FormProvider {...form}>
      <form className={cn("w-full", className)} {...props}>
        {children}
      </form>
    </FormProvider>
  );
}

export function FormField<TFormValues extends FieldValues, TName extends Path<TFormValues>>(props: UseControllerProps<TFormValues, TName> & { render: (args: { field: ControllerRenderProps<any, TName> }) => React.ReactNode }) {
  return <Controller {...props} />;
}

export function FormItem({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("space-y-2", className)} {...props}>
      {children}
    </div>
  );
}

export function FormLabel({ children, className, ...props }: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("text-sm font-medium leading-none", className)} {...props}>
      {children}
    </label>
  );
}

export function FormControl({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center", className)} {...props}>
      {children}
    </div>
  );
}

export function FormDescription({ children, className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-sm text-muted-foreground", className)} {...props}>
      {children}
    </p>
  );
}

export function FormMessage({ children, className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-sm text-red-500", className)} {...props}>
      {children}
    </p>
  );
}

export { FormControl as FormCtrl };
