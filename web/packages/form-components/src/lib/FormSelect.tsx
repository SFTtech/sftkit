import * as React from "react";
import { Select, SelectProps } from "@stustapay/components";
import { FormikProps } from "formik";

export type FormSelectProps<Name extends string, Values, Option, Multiple extends boolean> = {
  name: Name;
  formik: FormikProps<Values>;
} & Omit<SelectProps<Option, Multiple>, "onChange" | "error" | "helperText" | "value">;

export function FormSelect<
  Name extends string,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  Values extends Partial<Record<Name, any>>,
  Option,
  Multiple extends boolean,
>({ formik, name, ...props }: FormSelectProps<Name, Values, Option, Multiple>) {
  const { setFieldValue, setFieldTouched } = formik;
  const handleChange = React.useCallback(
    (value: unknown) => {
      setFieldValue(name, value, true);
      setFieldTouched(name, true, false);
    },
    [setFieldValue, setFieldTouched, name]
  );

  return (
    <Select
      variant={props.variant ?? "standard"}
      fullWidth={props.fullWidth ?? true}
      onChange={handleChange}
      value={formik.values[name]}
      error={formik.touched[name] && !!formik.errors[name]}
      helperText={(formik.touched[name] && formik.errors[name]) as string}
      {...props}
    />
  );
}
